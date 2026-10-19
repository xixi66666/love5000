# Skill Finder Remotion 渲染器

React + TypeScript + Remotion 4.0.536，作为 Skill Finder 内部媒体任务使用，不提供新的公网服务。
Vue 网站继续由原 FastAPI 托管。默认生成 1080×1920、30 FPS、H.264/AAC 视频和封面。

## 准备

安装 Node.js 22+、pnpm 11，以及系统 FFmpeg（含 ffprobe）。

```bash
cd website/skill-finder/video-renderer
pnpm install --frozen-lockfile
pnpm exec remotion browser ensure
pnpm run typecheck
pnpm test
```

也可通过 `REMOTION_BROWSER_EXECUTABLE` 指定已安装的 Chromium 完整路径。
安装器需要联网；不要关闭 TLS 校验。Remotion 依赖固定同一版本，升级时同步更新。

操作台模板编辑入口：`http://127.0.0.1:5177/daily-reports?panel=template`。
直接编辑 React/TSX、调整样式并在内嵌 Remotion Player 中预览，支持编译错误定位、保存启用与版本恢复。
详见 [模板编辑器](../docs/template-editor.md)。首次连接或源码编译使用 `scripts/build-editor.mjs`，
依赖同版本 `@remotion/player`、TypeScript 和 esbuild，不运行网页提供的构建配置。
可选独立 Studio：`pnpm studio`，其端口只供本地开发，不加入 website 服务 Dock。
开发示例不代表当天榜单或已发布内容。

## Python 调用

后端执行 `python -m app.daily.cli generate` 时，经 `app.daily.remotion` 调用：

```bash
node scripts/render.mjs /absolute/report/directory/render-manifest.json
```

清单由后端生成，包含场景、每段实际帧长、音轨、真实时间戳字幕、可选来源素材和字体。
还包含选中的 `theme` 和 `template_revision`；`REMOTION_TEMPLATE_DIR` 由后端指向校验过的私有版本源码。
编辑器保存时使用 `--check` 只渲染检查帧，正式任务仍完整输出音视频。
媒体路径必须位于同一份日报目录。渲染器仅在随机本机端口暴露明确列入清单的文件，
使用随机路由令牌，结束后关闭；不会托管报告 JSON、登录态或其他私有目录。

输出 `video.mp4`、`poster.png`、`render-result.json`；后端补充 `audio.m4a`、`subtitles.srt`，
继续沿用原日报审核和文件下载 API。

生成无数据库、无发布动作的能力样片：

```bash
cd website/skill-finder/backend
uv sync --extra captions
uv run python -m app.daily.cli sample
```

样片自动渲染随工程提供的动画作为 Remotion 本身的演示，无需预先准备私有素材库。
产物位于日报目录同级的 `video-samples/<timestamp>/`，不覆盖任何已审核成品。

## 配音与字幕

- 默认 `DAILY_TTS_PROVIDER=mimo`，需在后端私有 `.env` 设置 `MIMO_API_KEY`。
- MiMo 使用官方 `/v1/chat/completions`，合成文本放 assistant 消息，user 消息控制风格，返回 WAV。
- MiMo 配音经本地 faster-whisper 取得实际时间轴。首次下载多语种模型，`DAILY_WHISPER_MODEL`
  默认 small，可设成本地模型目录；离线部署提前准备缓存。字幕用原稿校正识别错误，
  保留实测意群边界；无法可靠对齐时失败，发布前仍必须试听核对。
- `DAILY_TTS_PROVIDER=edge` 显式使用原供应商，直接采集 WordBoundary 时间戳；不按字数估算。
- 新渲染器对人声做响度处理，目标约 -16 LUFS、真峰值 -1 dBTP；当前未内置商业配乐素材。

## 本地演示素材

在 `DAILY_ASSETS_DIR` 放置 `owner--repo.json`，例如 `remotion-dev--remotion.json`：

```json
{"file":"remotion-demo.mp4","source":"https://github.com/remotion-dev/remotion"}
```

`file` 必须是素材目录中的真实文件，可用 mp4/png/jpg/jpeg；`source` 必须是可追溯的 HTTPS 来源。
生成时将素材复制到该期日报，避免渲染期间变更。不抓取任意远程 URL，不允许路径穿越。
默认 `DAILY_REQUIRE_DEMO_ASSETS=true`，项目缺少来源素材时直接阻止生成，且在调用配音前检查。
仅需调试资料解读版时可显式设为 false；此时显示“资料解读 · 未提供实机演示”，
并在渲染结果记录缺失数量，不伪造实机画面。

`RenderDemo` 是随代码提供的本地动画演示 Composition，用于展示 Remotion 本身的实际输出。
它不是其他项目的实机演示，也不包含榜单增长数据。

## 部署

从微服务根目录使用 `deploy/Dockerfile` 构建，镜像包含 Node、锁定的渲染依赖、Chromium、
FFmpeg 与中文字体。API 端口不变。运行目录必须可写；离线缓存通过 HF_HOME 配置到持久卷。
模板版本与生效指针在日报目录同级 `video-template/`，默认随现有 backend/data 卷持久化。
升级镜像不会覆盖私有模板版本；升级固定数据协议前需核对自定义源码兼容性。
`run-cloud.sh` 对新建容器默认预留 3g 内存 / 4g 含 swap / 2 CPU；可通过
`SKILL_FINDER_MEMORY`、`SKILL_FINDER_MEMORY_SWAP`、`SKILL_FINDER_CPUS` 调整。
既有容器不会被脚本自动改配，升级前核对主机资源。`REMOTION_CONCURRENCY` 默认 2，
可设为 1–8；它控制帧渲染并发，不能据此直接推算整个任务的内存占用。

Remotion 使用特殊许可证，个人、小团队与公司场景以官方条款为准：
https://www.remotion.dev/docs/license/pricing 。
