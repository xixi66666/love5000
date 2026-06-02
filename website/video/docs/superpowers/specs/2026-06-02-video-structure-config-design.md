# Video 项目结构与配置管理改造设计

## 目标

`website/video` 当前同时包含 Web 服务入口、命令行入口、核心 Python 包、实验脚本、正式测试、本地配置、静态页面、运行产物和本地依赖，目录职责不够清晰。此次改造目标是先把边界整理清楚，降低后续扩展 TTS、图片、视频模型接口时的维护成本，并为未来改造成 Java 微服务预留稳定调用边界。

本次设计只处理 `website/video` 独立 Python 微应用内部结构，不把它加入 Maven modules，也不把视频生成、FFmpeg、OpenAI 或 TTS 业务逻辑改写进 Java Controller。

## 范围

本次改造包含：

1. 删除正式测试目录 `website/video/tests/`。
2. 将手动验证脚本从测试语义中剥离，统一迁入脚本目录并使用 `smoke_*.py` 或 `check_*.py` 命名。
3. 将配置文件集中到 `website/video/config/`。
4. 在 Web 页面中提供本地配置查看和编辑能力。
5. 将 Python 核心脚本集中到 `website/video/python/`，方便未来 Java 微服务调用和管理。
6. 保留根目录 `web_server.py` 和 `anime_cli.py` 作为兼容入口，避免破坏 `website` 自动启动器和现有命令。
7. 同步更新 README、AGENTS 和 `.gitignore` 中的路径说明。

本次改造不包含：

- 引入 FastAPI、Flask、Vue 或 React。
- 将 Python 逻辑迁移到 Java。
- 增加新的真实外部 API 调用能力。
- 改造 `website` 的 Java 自动启动逻辑，除非兼容入口无法满足启动需求。
- 提交 `config.local.json`、`.vendor/`、`anime_projects/`、日志、缓存或真实 API Key。

## 推荐目录结构

改造后目录如下：

```text
website/video/
├── config/
│   ├── config.example.json
│   └── config.local.json
├── python/
│   ├── anime_tools/
│   ├── cli/
│   │   └── anime_cli.py
│   ├── server/
│   │   └── web_server.py
│   └── scripts/
│       ├── create_default_bgm.py
│       ├── generate_modelscope_project_video.py
│       └── smoke_modelscope_i2v.py
├── web/
├── assets/
├── anime_projects/
├── docs/
├── anime_cli.py
└── web_server.py
```

职责划分：

- `config/`：集中保存配置模板和本地私有配置。`config.local.json` 继续禁止提交。
- `python/anime_tools/`：核心业务能力包，包括项目管理、配置读取、OpenAI 兼容接口、TTS、ModelScope、渲染、任务管理和 Web API。
- `python/cli/anime_cli.py`：真正的命令行实现。
- `python/server/web_server.py`：真正的本地 Web 服务实现。
- `python/scripts/`：手动验证、一次性生成、辅助脚本。手动外部接口验证使用 `smoke_*.py` 命名，不再放入 `tests/`。
- 根目录 `anime_cli.py`：兼容入口，转调 `python/cli/anime_cli.py`。
- 根目录 `web_server.py`：兼容入口，转调 `python/server/web_server.py`，继续支持 `python web_server.py`。
- `web/`：原生 HTML/CSS/JavaScript 工作台页面。
- `assets/`：默认 BGM 等静态素材。
- `anime_projects/`：本地生成项目和视频产物，继续禁止提交。

## 配置文件设计

默认配置路径改为：

```text
website/video/config/config.local.json
```

配置模板路径改为：

```text
website/video/config/config.example.json
```

为兼容旧命令，短期内允许继续读取根目录：

```text
website/video/config.local.json
```

读取优先级：

1. 用户通过命令行或 API 显式传入的配置路径。
2. `website/video/config/config.local.json`。
3. `website/video/config.local.json`。

保存策略：

- Web 页面保存配置时只写入 `website/video/config/config.local.json`。
- 如果 `config/` 不存在，后端自动创建。
- 如果本地配置不存在，后端可以基于 `config/config.example.json` 创建一个不含真实密钥的初始配置。
- 配置写入必须使用临时文件加原子替换，避免保存中断导致 JSON 损坏。

## 页面配置编辑能力

新增本地配置 API：

```text
GET  /api/config
POST /api/config
```

`GET /api/config` 返回当前配置，但必须隐藏敏感字段：

```json
{
  "success": true,
  "config_path": "config/config.local.json",
  "config": {
    "openai": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "",
      "text_model": "gpt-4.1-mini",
      "image_model": "gpt-image-1",
      "tts_model": "gpt-4o-mini-tts",
      "tts_voice": "alloy"
    },
    "tts": {
      "provider": "openai"
    },
    "tencent_tts": {
      "secret_id": "",
      "secret_key": "",
      "region": "ap-guangzhou",
      "voice_type": 101001,
      "primary_language": 1,
      "codec": "mp3",
      "sample_rate": 16000,
      "speed": 0,
      "volume": 5
    },
    "modelscope_video": {
      "api_key": "",
      "base_url": "https://dashscope.aliyuncs.com/api/v1",
      "model": "wanx2.1-i2v-plus",
      "duration": 5,
      "resolution": "720P",
      "poll_interval_seconds": 5,
      "timeout_seconds": 600
    },
    "assets": {
      "default_bgm": "assets/default_bgm.mp3"
    }
  }
}
```

敏感字段包括：

- `openai.api_key`
- `tencent_tts.secret_id`
- `tencent_tts.secret_key`
- `modelscope_video.api_key`

`POST /api/config` 保存规则：

- 非敏感字段按页面提交值覆盖。
- 敏感字段为空字符串时保留旧值。
- 敏感字段填写新值时才覆盖旧值。
- 不在响应、日志、错误消息中输出真实密钥。
- `tts.provider` 当前允许 `openai` 或 `tencent`，后续可扩展更多 provider。
- 数字字段需要做类型转换和范围校验，例如超时时间、采样率、语速、音量。

前端设计：

- 在现有配置文件输入区域附近增加“配置”面板。
- 使用表单编辑常用项，例如 base_url、模型名、TTS provider、腾讯云音色、ModelScope 模型和默认 BGM。
- 密钥输入框使用 password 类型，placeholder 显示“留空则保留现有密钥”。
- 保存成功后显示明确状态，不弹出真实密钥。
- 生成、续跑、重生关键帧等操作默认使用 `config/config.local.json`。

## Java 微服务迁移预留

当前 Java 侧保持现有职责：

- 提供主页入口。
- 自动启动或复用 `video`。
- 健康检查 `GET http://127.0.0.1:5176/api/health`。
- 不在 Java Controller 中实现视频生成业务。

为了未来 Java 微服务调用 Python 脚本，本次整理后保持以下稳定边界：

```text
python web_server.py
python anime_cli.py auto "<theme>"
python python/scripts/smoke_modelscope_i2v.py
GET  /api/health
GET  /api/config
POST /api/config
POST /api/projects/auto
POST /api/projects/{project_name}/resume
POST /api/projects/{project_name}/render
```

未来 Java 微服务可以有两种迁移路径：

1. 继续通过 `ProcessBuilder` 调用 `python/cli/anime_cli.py` 或 `python/scripts/*.py`。
2. 将 Python 服务作为独立本地微服务保留，Java 通过 HTTP 调用 `/api/**`。

本次目录改造不强迫选择其中一种，只让脚本边界更清楚。

## 删除测试与手动验证策略

按用户确认，本次采用 C 方案：

- 删除 `website/video/tests/`。
- 不保留正式单元测试命令。
- 将 `scripts/test_modelscope_i2v.py` 改名为 `python/scripts/smoke_modelscope_i2v.py`。
- 将其他脚本迁入 `python/scripts/`。
- README 中把验证方式改成手动验证：

```bash
cd website/video
python web_server.py
```

然后访问：

```text
http://127.0.0.1:5176/
http://127.0.0.1:5176/api/health
```

涉及外部接口时使用：

```bash
python python/scripts/smoke_modelscope_i2v.py --config config/config.local.json
```

风险说明：

- 删除正式测试会降低回归保护能力。
- 后续每次改动 `web_api.py`、配置保存、路径安全、任务管理和渲染流程时，需要更认真做手动验证。
- 如果项目继续扩大，建议重新引入测试，但可以放在未来 Java 微服务或新的 Python 测试目录中。

## 兼容性要求

改造完成后必须继续满足：

```bash
cd website/video
python web_server.py
python anime_cli.py auto "雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪"
```

根入口需要主动把 `website/video/python` 加入 `sys.path`，确保迁移后的 `anime_tools` 可以正常 import。

`VideoAutoStartRunner` 当前启动命令仍为：

```text
python web_server.py
```

因此根目录 `web_server.py` 必须保留，不能直接删除。

## 安全要求

- 不提交真实 API Key、腾讯云 SecretId、腾讯云 SecretKey、DashScope API Key。
- 不把敏感字段返回给前端。
- 不把敏感字段写入日志、任务记录、错误消息或 README。
- 配置 API 只用于本地工作台，服务继续默认绑定 `127.0.0.1`。
- 配置路径不允许任意写入系统目录，页面保存只写 `config/config.local.json`。
- 保留项目名和资源路径的路径穿越校验。

## 验收标准

1. `website/video/tests/` 已删除。
2. 手动验证脚本迁入 `website/video/python/scripts/`，测试语义脚本改为 `smoke_*.py`。
3. `config.example.json` 迁入 `website/video/config/`。
4. `.gitignore` 忽略 `config/config.local.json`、`.vendor/`、`anime_projects/`、缓存和日志。
5. `python web_server.py` 仍可启动 `5176` 服务。
6. `GET /api/health` 返回 `success=true`。
7. 页面可以读取并保存配置。
8. 页面不会展示真实密钥。
9. 自动生成、续跑、关键帧重生等流程默认使用 `config/config.local.json`。
10. README 和 AGENTS 中的目录、启动、配置、验证说明已同步。

