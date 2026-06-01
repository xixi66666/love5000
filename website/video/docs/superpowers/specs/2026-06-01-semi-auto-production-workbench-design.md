# 半自动生产工作台设计文档

## 目标

在现有 Python 命令行工具基础上，新增一个本地 Web 半自动生产工作台，让用户可以通过浏览器完成 AI 动漫短片的生成、检查、编辑、单镜头关键帧重生、字幕生成、视频合成和结果预览。

第一版目标不是做完整剪辑软件，而是把当前 `anime_cli.py` 已有能力变成可视化、可操作、可恢复的生产界面。核心价值是减少命令行操作，让每个项目的素材、分镜、提示词、输出视频和错误日志都能在一个界面里被看见和处理。

## 已有基础

当前项目已经具备可复用的核心模块：

- `anime_tools.auto_pipeline.AutoPipeline`：自动生成项目、分镜、关键帧、配音、字幕和最终视频。
- `anime_tools.project`：项目初始化、分镜读取、素材检查、字幕生成、手动剪辑指南生成。
- `anime_tools.render`：根据关键帧、旁白、BGM 和字幕合成 `output/final.mp4`。
- `anime_tools.openai_client.OpenAICompatibleClient`：调用兼容 OpenAI 的文本、图片、语音接口。
- `anime_cli.py`：现有命令行入口，后续继续保留。

因此工作台采用“新增 Web 层，复用核心逻辑”的方式，不重写生成流程。

## 第一版范围

第一版工作台包含以下能力：

1. 浏览 `anime_projects` 下已有项目。
2. 输入主题并创建自动生成任务。
3. 对已有项目执行续跑。
4. 查看项目详情，包括标题、旁白、分镜、关键帧、音频、字幕、最终视频。
5. 编辑镜头的描述、字幕、时长和 `image_prompt`。
6. 对单个镜头重新生成关键帧图片。
7. 重新生成字幕文件。
8. 重新合成最终视频。
9. 查看任务状态、任务日志、生成警告和错误信息。
10. 下载或打开最终视频路径。

第一版暂不包含：

- 多任务并发生成。
- 拖拽时间线剪辑。
- 真正的图生视频 API。
- 用户登录和权限管理。
- 云端部署。
- Vue、React 或桌面壳。

## 技术方案

采用本地 Python HTTP 服务加原生 HTML/CSS/JavaScript。

```text
浏览器页面
  -> 本地 Python HTTP API
  -> anime_tools 核心模块
  -> anime_projects 项目目录
  -> 图片、字幕、日志、final.mp4 返回给浏览器预览
```

推荐新增文件结构：

```text
web_server.py
anime_tools/
  web_api.py
  task_manager.py
web/
  index.html
  app.css
  app.js
```

职责划分：

- `web_server.py`：启动本地 HTTP 服务，绑定 `127.0.0.1`。
- `anime_tools/web_api.py`：处理 HTTP 路由、参数校验、JSON 响应和静态文件访问。
- `anime_tools/task_manager.py`：管理长任务状态、日志、错误和互斥执行。
- `web/index.html`：页面结构。
- `web/app.css`：Linear 风格视觉实现。
- `web/app.js`：请求 API、渲染项目、编辑表单、轮询任务状态。

第一版可以优先使用 Python 标准库 `http.server` 实现，避免引入第三方依赖。若后续接口复杂度明显上升，再迁移到 FastAPI。

## 信息架构

工作台使用三栏结构，适合桌面生产场景。

```text
┌──────────────────────────────────────────────────────────┐
│ 顶部栏：产品名、当前任务状态、全局操作                   │
├──────────────┬──────────────────────────┬────────────────┤
│ 项目列表      │ 镜头工作区                │ 预览和日志       │
│ 新建生成      │ 镜头卡片                  │ 视频预览         │
│ 项目状态      │ 编辑描述/字幕/提示词       │ 当前任务日志     │
│ 最近输出      │ 重生关键帧                │ 错误和警告       │
└──────────────┴──────────────────────────┴────────────────┘
```

左侧栏：

- 项目列表。
- 新建项目入口。
- 项目搜索。
- 项目状态徽标，例如 `已完成`、`缺素材`、`生成中`、`失败`。

中间主区：

- 当前项目标题和旁白编辑区。
- 镜头卡片列表，数量由 `storyboard.json` 中的 `shots` 动态决定。
- 每个镜头卡片展示关键帧缩略图、镜头 ID、时长、字幕、描述、图片提示词。
- 每个镜头提供“保存镜头”和“重生关键帧”操作。
- 长时间动画项目可能包含几十个镜头，镜头列表需要支持滚动、折叠和按镜头 ID 快速定位。

右侧栏：

- `output/final.mp4` 竖屏视频预览。
- 字幕文件状态。
- BGM 和旁白文件状态。
- 当前任务日志。
- `generation_warnings.md` 或错误信息。

## Linear 风格规则

界面采用 `awesome-design-md` 中的 Linear 风格，定位为深色、克制、高密度的生产工具。

颜色：

- 页面背景使用 `#010102`。
- 一级面板使用 `#0f1011`。
- 二级面板和 hover 使用 `#141516`。
- 分割线和边框使用 `#23252a`。
- 主要文字使用 `#f7f8f8`。
- 次要文字使用 `#d0d6e0`。
- 弱提示文字使用 `#8a8f98`。
- 主强调色使用 Linear lavender `#5e6ad2`。
- 主按钮 hover 使用 `#828fff`。
- 成功状态可少量使用 `#27a644`。

排版：

- 字体优先使用 `Inter`，其次使用 `-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif`。
- 页面标题 22px 到 28px，字重 600。
- 面板标题 14px 到 16px，字重 500。
- 正文 14px 到 16px。
- 日志和路径使用等宽字体 `ui-monospace, SFMono-Regular, Consolas, monospace`。

形状和间距：

- 按钮和输入框圆角 8px。
- 面板圆角 12px。
- 视频预览和关键帧容器圆角 16px。
- 使用 4px 基础间距体系：4、8、12、16、24、32。
- 尽量使用细边框和表面层级，不使用重阴影。

交互风格：

- 紫色只用于主操作、焦点环、当前选中项和少量链接。
- 不使用渐变背景、装饰光斑或多彩强调色。
- 按钮点击后必须进入 loading 或 disabled 状态。
- 输入框 focus 使用紫色描边。
- 任务状态用简洁 badge 表示。
- 页面优先展示产品 UI 和素材预览，不做营销页式大标题。

## 核心交互流程

### 新建生成

1. 用户在左侧输入主题。
2. 点击“生成项目”。
3. 后端创建后台任务。
4. 页面进入生成中状态，右侧显示实时日志。
5. 任务完成后刷新项目列表，自动选中新项目。
6. 右侧显示最终视频或错误原因。

### 续跑项目

1. 用户选择一个已有项目。
2. 点击“续跑”。
3. 后端调用 `AutoPipeline.resume(project_dir)`。
4. 已存在的关键帧和音频会被跳过，只补齐缺失素材并重新合成。
5. 页面更新任务日志和最终视频。

### 编辑镜头

1. 用户打开项目详情。
2. 在镜头卡片中修改描述、字幕、时长或 `image_prompt`。
3. 点击“保存镜头”。
4. 后端更新 `storyboard.json`，并同步更新 `script/image_prompts.json`。
5. 页面显示保存成功状态。

### 单镜头重生关键帧

1. 用户修改某个镜头的 `image_prompt`。
2. 点击“重生关键帧”。
3. 后端读取配置和 API Key，调用 `OpenAICompatibleClient.generate_image(prompt)`。
4. 新图片覆盖 `assets/keyframes/{shot_id}.png`。
5. 页面刷新该镜头缩略图。
6. 用户可继续点击“重新合成视频”。

### 重新合成视频

1. 用户点击“重新合成”。
2. 后端先调用 `generate_subtitles(project_dir)`。
3. 再调用 `render_image_storyboard(project_dir, storyboard)`。
4. 成功后刷新 `output/final.mp4` 预览。

## API 设计

所有接口只监听本机，不对公网开放。

```text
GET  /api/projects
GET  /api/projects/{project_name}
POST /api/projects/auto
POST /api/projects/{project_name}/resume
POST /api/projects/{project_name}/storyboard
POST /api/projects/{project_name}/shots/{shot_id}/regenerate-keyframe
POST /api/projects/{project_name}/subtitles
POST /api/projects/{project_name}/render
GET  /api/tasks/{task_id}
GET  /api/assets/{project_name}/keyframes/{file_name}
GET  /api/assets/{project_name}/video/final
```

`POST /api/projects/auto` 请求体：

```json
{
  "theme": "雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪",
  "config_path": "D:\\Code\\video\\config.local.json",
  "bgm_path": ""
}
```

`POST /api/projects/{project_name}/storyboard` 请求体：

```json
{
  "title": "雨刀妖影",
  "narration": "雨夜里，刀光救下了路人。可他抬头时，才看见她的影子并非人形。",
  "shots": [
    {
      "id": "shot_01",
      "duration": 3.5,
      "description": "雨夜巷口，路人被黑影逼近。",
      "subtitle": "雨夜里，他被黑影逼到墙角。",
      "image_prompt": "国风动漫，雨夜巷口，黑影逼近路人，竖屏构图"
    }
  ]
}
```

`GET /api/tasks/{task_id}` 响应：

```json
{
  "id": "task_20260601_150000",
  "type": "render",
  "status": "running",
  "project_name": "20260601_141630_雨刀妖影",
  "logs": ["开始生成字幕", "开始调用 FFmpeg"],
  "error": "",
  "created_at": "2026-06-01T15:00:00",
  "finished_at": ""
}
```

## 任务模型

任务状态：

- `queued`：已创建，等待执行。
- `running`：正在执行。
- `success`：执行成功。
- `failed`：执行失败。

第一版只允许同一时间运行一个长任务，避免同时调用 AI 接口或 FFmpeg 造成资源抢占。若已有任务正在运行，新的生成、续跑、重生关键帧和重新合成操作应返回明确错误。

任务日志保存在内存中，同时可以按需写入项目目录下的 `output/workbench_task_log.md`，方便异常后排查。

## 数据写入规则

编辑分镜时需要保持以下文件一致：

- `storyboard.json`
- `script/narration.txt`
- `script/title.txt`
- `script/image_prompts.json`

保存规则：

1. 先校验请求数据。
2. 再写入临时文件。
3. 临时文件写入成功后替换正式文件。
4. 如果写入失败，保留旧文件。

镜头数量不能写死。第一版应以 `storyboard.json` 中的 `shots` 数组为准，动态渲染任意数量镜头。

镜头 ID 不强制限定固定范围，但必须在同一个项目内唯一。推荐继续使用 `shot_01`、`shot_02`、`shot_03` 这类递增命名，便于排序、素材定位和日志排查。

第一版至少支持编辑、保存和重生已有镜头。新增、删除、排序镜头可以作为第二阶段能力，但数据结构和界面布局不能阻碍后续扩展。

## 参数校验

后端需要校验：

- `theme` 不能为空，长度建议不超过 300 字。
- `project_name` 不能包含路径穿越字符，例如 `..`、`/`、`\`。
- `shot_id` 必须存在于当前 `storyboard.json`。
- `shots` 必须是非空数组，且镜头 ID 在同一项目中不能重复。
- `duration` 必须大于 0，建议不超过 30 秒。
- `subtitle`、`description`、`image_prompt` 不能为空。
- `config_path` 默认使用项目根目录下的 `config.local.json`。
- API Key 不返回给前端，不写入日志。

## 错误处理

界面需要区分以下错误：

- 缺少 `config.local.json`。
- `openai.api_key` 未配置。
- 默认 BGM 文件不存在。
- AI 文本接口失败。
- AI 图片接口失败。
- TTS 接口失败。
- FFmpeg 不存在或合成失败。
- 项目文件缺失或 JSON 格式错误。

错误展示原则：

- 对用户显示中文可理解原因。
- 对开发者保留简短技术细节。
- 不展示 API Key。
- 长错误放入日志面板，不用弹窗遮挡主要工作区。

## 响应式设计

第一版以桌面浏览器为主，推荐最小宽度 1280px。

桌面：

- 三栏布局。
- 左侧项目栏固定宽度约 280px。
- 右侧预览栏固定宽度约 360px。
- 中间镜头工作区自适应。

窄屏：

- 左侧项目栏折叠为顶部项目选择器。
- 右侧预览移动到镜头列表下方。
- 镜头卡片单列显示。

## 可访问性和可用性

- 所有输入框必须有可见 label。
- 所有按钮必须有明确文本。
- loading 状态下按钮禁用，防止重复提交。
- 错误信息显示在相关区域附近。
- 支持键盘 Tab 顺序访问主要操作。
- 焦点状态清晰可见。
- 图片需要 `alt` 文本，说明镜头 ID 或状态。
- 视频预览需要原生 controls。

## 验收标准

第一版完成后应满足：

1. 可以启动本地服务并打开工作台首页。
2. 可以列出已有 `anime_projects` 项目。
3. 可以选择项目并查看分镜、关键帧、字幕和最终视频。
4. 可以输入主题创建自动生成任务。
5. 可以对项目执行续跑。
6. 可以编辑镜头字段并保存到项目文件。
7. 可以单独重生某个镜头的关键帧。
8. 可以重新生成字幕。
9. 可以重新合成最终视频。
10. 可以在界面查看任务状态、日志和错误。
11. API Key 不会出现在前端响应、日志或页面文本中。
12. 现有命令行功能仍可使用。
13. 现有单元测试继续通过。

## 测试策略

单元测试：

- 项目列表读取。
- 分镜保存。
- 路径安全校验。
- 任务状态流转。
- 关键帧重生调用 fake client。
- 重新合成调用 fake command runner。

接口测试：

- `/api/projects` 返回项目列表。
- `/api/projects/{project_name}` 返回详情。
- 非法项目名返回 400。
- 缺配置返回清晰错误。
- 长任务接口返回 task id。
- 任务状态接口可查询日志和结果。

手工验证：

```bash
python -m unittest discover -s tests -v
python web_server.py
```

然后打开：

```text
http://127.0.0.1:5175
```

在页面中验证项目浏览、镜头保存、关键帧重生、字幕生成、视频合成和日志展示。

## 后续扩展

后续可以在第一版稳定后增加：

- Vue 前端重构。
- 多任务队列。
- 单镜头重生文本内容。
- 接入图生视频 API。
- 镜头新增、删除、排序。
- 时间线式剪辑预览。
- 导出剪映草稿。
- 批量生成主题队列。
- 项目归档和搜索标签。
