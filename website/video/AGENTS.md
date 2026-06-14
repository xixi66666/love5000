# AGENTS.md

## 项目概述

`website/video` 是 `love5000` 当前接入的 AI 原创动漫短片生成工作台，作为独立 Python 微应用运行，默认端口 `5176`。它不是 Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。

## 模块边界

- 兼容入口：`anime_cli.py`、`web_server.py`。
- 核心代码：`python/anime_tools/`，包含项目管理、OpenAI 兼容接口、TTS、图生视频 Provider、FFmpeg 合成、任务管理和 Web API。
- CLI 代码：`python/cli/`。
- 本地 HTTP 服务代码：`python/server/`。
- 辅助脚本：`python/scripts/`，外部接口冒烟脚本使用 `smoke_*.py` 命名。
- 前端页面：`web/`。
- 配置模板：`config/config.example.json`。
- 本地生成产物：`anime_projects/`，默认不提交。
- Java 侧只负责入口链接、健康检查和自动启动，不把视频生成、FFmpeg 调用或 OpenAI 调用改写进 Controller。

## 命令

```bash
cd website/video
python -m unittest discover -s tests -v
python web_server.py
```

健康检查：

```text
GET http://127.0.0.1:5176/api/health
GET http://127.0.0.1:5176/api/config
```

## 配置与安全

- 本机私有配置写入 `config/config.local.json`，禁止提交。
- 历史兼容位置 `config.local.json` 也禁止提交真实 Key。
- 不提交 `.vendor/`、`__pycache__/`、`.pytest_cache/`、`anime_projects/`、生成的视频、音频、图片产物或真实 API Key。
- 视频生成输出必须保留 AI 生成内容和非真实拍摄素材边界。

## 文档同步

每次修改 Web API、命令行参数、配置结构、外部 Provider、项目输出结构、测试方式或与 `website` 的自动启动集成时，必须同步更新本文件、本目录 README，以及根目录和 `website` 模块的 `AGENTS.md` / `README.md`。
