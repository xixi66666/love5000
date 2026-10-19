# Remotion 接入与运行

全流程可视化入口及模板开发说明见 [制作操作台](production-console.md)。
React/TSX 源码与可视化样式可在操作台直接编辑、编译预览、保存启用与恢复版本，见 [模板编辑器](template-editor.md)。

## 已实现的边界

- 内部 `video-renderer/` 为 Node.js 22+、React、TypeScript、Remotion 4.0.536 工程；不加入 Maven，
  不新增服务端口或 Dock 卡片。Vue 页面、现有日报 API、审核哈希和发布流程继续复用。
- 默认 `DAILY_VIDEO_RENDERER=remotion`，生产目标 1080×1920 / 30 FPS / H.264 + AAC。
- 默认 `DAILY_TTS_PROVIDER=mimo`，MiMo 配置仅放 `backend/.env` 或环境变量；不在 Git 中保存凭据。
- 字幕从实际 MiMo 音轨用 faster-whisper 取得时间轴，再对齐原稿修正专有名词与繁简识别错误；
  无法可靠对齐时失败。保留 Edge 的真实词边界适配。
- 人声响度处理约 -16 LUFS / 真峰值 -1 dBTP；未随代码提供配乐或外部项目演示素材。
- 这是渲染接入，不代表所有项目的演示素材、口播编辑和配音风格已经达到用户验收标准。

## 本机准备

```powershell
cd website/skill-finder/video-renderer
pnpm install --frozen-lockfile
pnpm exec remotion browser ensure
pnpm run typecheck
pnpm test

cd ../backend
uv sync --extra captions
uv run python -m app.daily.cli sample
```

FFmpeg 和 ffprobe 必须在 PATH；也可分别配置 `DAILY_FFMPEG_COMMAND`、`DAILY_FFPROBE_COMMAND`。
Node 不在 PATH 时配置 `DAILY_NODE_COMMAND` 为解释器完整路径。
已有浏览器可通过 `REMOTION_BROWSER_EXECUTABLE` 指定完整路径。
以上命令从仓库根目录开始；本机 Python 要求 >=3.11，默认系统旧 Python 不适用。

MiMo 私有配置示例（真实密钥只写到被忽略的文件）：

```dotenv
DAILY_VIDEO_RENDERER=remotion
DAILY_TTS_PROVIDER=mimo
MIMO_API_KEY=replace_with_your_private_key
MIMO_API_BASE=https://api.xiaomimimo.com/v1
MIMO_TTS_MODEL=mimo-v2.5-tts
MIMO_TTS_VOICE=苏打
DAILY_WHISPER_MODEL=small
DAILY_REQUIRE_DEMO_ASSETS=true
REMOTION_CONCURRENCY=2
```

`MIMO_TTS_STYLE` 可调整表演指令。默认快节奏中文科技工具推荐，突出用途与效果，保留气口。
MiMo 官方协议是 `POST /chat/completions`，以 assistant 消息传合成文本，返回 Base64 WAV。
它没有在当前文档承诺字词时间戳，因此本项目对真实音频转写，不能以字数均分时长替代。
字幕采用原稿文字和 ASR 实测意群边界，不生成逐字高亮。发布前仍需试听核对；
默认 small 模型在 CPU 上运行，支持本地模型路径。
首次下载 Whisper 模型后可复用 `HF_HOME` 缓存，云端应指向持久卷，如 `/data/huggingface`。

## 素材与输出

`DAILY_ASSETS_DIR` 默认 `backend/data/video-assets`（相对于后端工作目录）。
每个项目使用 `owner--repo.json` 声明本地 mp4/png/jpg/jpeg 文件和 HTTPS 来源：

```json
{"file":"demo.mp4","source":"https://github.com/owner/repo"}
```

文件不能越出素材目录，生成时复制到该期日报并固化。默认要求每个项目有来源素材，
缺失时在配音调用前失败；显式调试降级 `DAILY_REQUIRE_DEMO_ASSETS=false` 会标注资料解读。
不能把示意动画或其他项目视频当作被介绍项目的实际演示。

输出仍为原目录中的 `video.mp4`、`audio.m4a`、`poster.png`、`subtitles.srt`、`script.txt`、`report.md`。
新增私有工作文件 `render-manifest.json`、`render-result.json`、`.remotion-bundle/` 和每段音频、来源素材。
API 不公开新工作文件。报告增加可选 `render` 元数据：renderer、分辨率、帧率、时长、缺素材数、TTS 供应商。

样片使用 `python -m app.daily.cli sample`，不访问数据库、不创建发布任务、不覆盖已审核日报。
输出到 `DAILY_REPORTS_DIR` 同级 `video-samples/<timestamp>/`。
样片命令先自动渲染工程提供的 `RenderDemo` Composition，将其存入本次样片的独立素材目录，
作为 Remotion 自身的能力演示；不要求预先准备私人素材库。
样片内容与当天榜单分开，不虚构排名或 Star 数。

## 回退、测试、部署

`DAILY_VIDEO_RENDERER=legacy` 显式回退原 Pillow + Edge TTS + FFmpeg 路径。新渲染器失败不会自动
切换供应商或输出静音视频。既有已审核报告保持不可变；不要删除批准记录以强制重新生成。

后端执行 `uv run python -m ruff check .`、`uv run python -m pytest -q`；pytest 仅收集 `tests/`，
不扫描被忽略的数据、依赖缓存或第三方源码。MySQL 集成测试仍要求独立 TEST_DATABASE_URL。
渲染器执行 `pnpm run typecheck` 和 `pnpm test`，并以真实成片做视觉、字幕和声音检查。

`deploy/Dockerfile` 现在包含 Node 构建阶段、固定渲染依赖、Chromium 和字幕转写依赖。
`deploy/requirements.lock` 从 `uv.lock` 带 `--extra captions` 导出。
新容器 `run-cloud.sh` 默认 3g 内存、4g 含 swap、2 CPU、512m 临时目录；先确认宿主资源，
可用 `SKILL_FINDER_MEMORY` / `SKILL_FINDER_MEMORY_SWAP` / `SKILL_FINDER_CPUS` 覆盖。
脚本不会重建既有容器；没有自动部署本次代码到服务器，也没有变更现有定时任务。

详细模板说明见 `../video-renderer/README.md`。Remotion 特殊许可条款需按实际使用主体核对。
