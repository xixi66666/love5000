# HyperFrames 视频引擎

HyperFrames 作为独立可切换引擎接入 Skill Finder，替代画面编排和渲染部分。
原榜单、素材固化、MiMo/Edge 配音、真实时间戳字幕、FFmpeg 音频母带、审核与发布流程继续复用。
原 Remotion 和 legacy 保留显式选择；失败时不会自动换引擎或供应商。

## 准备与选择

新增内部工程 `hyperframes-renderer/`，不作为微服务，不新增端口、Maven 模块或首页 Dock 入口。
依赖固定为 `@hyperframes/producer`、`@hyperframes/engine`、`@hyperframes/core` 0.8.186、GSAP 3.13.0 和 linkedom 0.18.12。
需要 Node.js 22+、FFmpeg/ffprobe 和 Chrome/Chromium。

```powershell
cd website/skill-finder/hyperframes-renderer
npm ci
npm run check
npm test
```

在后端私有环境配置中选择：

```dotenv
DAILY_VIDEO_RENDERER=hyperframes
HYPERFRAMES_CONCURRENCY=1
# 本机已安装浏览器时填写实际完整路径；Docker 已配置 /usr/bin/chromium
HYPERFRAMES_BROWSER_EXECUTABLE=C:/path/to/chrome-headless-shell.exe
```

`DAILY_NODE_COMMAND`、`DAILY_FFMPEG_COMMAND`、`DAILY_FFPROBE_COMMAND`、配音、字幕模型和可选 BGM 配置沿用现有约定。
`HYPERFRAMES_CONCURRENCY` 范围 1–8，默认 1；增加并发前先核对内存和 CPU。
默认引擎为 HyperFrames，既有 `.env` 配置优先；本机已显式配置 HyperFrames、浏览器和媒体工具，重启 5177 后新任务使用 HyperFrames。
Remotion 作为备用项保留：需要时设置 `DAILY_VIDEO_RENDERER=remotion` 并重启服务；两套模板、依赖与版本均保留，不自动重跑失败任务。已生成视频和已批准版本不重新渲染。

## 模板编辑与预览

操作台入口继续是 `/daily-reports?panel=template`，会显示当前引擎及对应源码。
HyperFrames 编辑白名单为 `src/template.html` 和 `src/demo.html`，主题字段继续使用现有颜色、字号、安全区等配置。
`src/template-defaults.json` 是默认主题来源，不通过网页直接编辑。
模板编译使用工程可信脚本，不执行用户提供的 npm 构建配置。

模板 API 在既有路径上增加引擎标识：

- `GET /api/v1/daily-reports/template?engine=hyperframes` 读取模板；省略时读取当前引擎。
- `PUT /api/v1/daily-reports/template` 和 `POST .../template/preview` 的 JSON 草稿包含 `engine`、`expected_revision`、`sources`、`theme`。
- 恢复版本时同样绑定引擎与预期版本；旧未携带引擎的 Remotion 草稿保持兼容。
- 预览静态资源使用 `/template/engines/{engine}/previews/{id}/...`，引擎路径隔离两套缓存；原 `/template/previews/{id}/...` 继续兼容 Remotion。

源码、预览和保存继续要求 X-Admin-Key 与 HTTPS/本机连接；不会将管理密钥传入预览 iframe。
HyperFrames 模板版本和生效指针位于 `DAILY_REPORTS_DIR` 同级 `video-template/hyperframes/`。
原 Remotion 的 `video-template/active.json` 和已有版本继续有效，两种引擎的保存和恢复互不覆盖。

## 制作过程与数据

```powershell
cd website/skill-finder/backend
# 确认 DAILY_VIDEO_RENDERER 已选择 hyperframes
uv run python -m app.daily.cli sample
```

该命令生成无数据库、无发布动作的引擎能力样片，会调用已配置的配音服务。
正式每日视频继续使用页面一键制作或 `python -m app.daily.cli generate`。

内部调用协议：

```text
node hyperframes-renderer/scripts/render.mjs /absolute/report/render-manifest.json
```

`--demo` 生成项目自身的演示素材，`--check` 执行短帧检查。
渲染器通过官方 producer/engine API 执行 HyperFrames 渲染，不是自行截帧冒充引擎。
每次生成临时的 `.hyperframes-project-*` 隔离目录，只固化清单中的媒体、字体、本地 GSAP 和选定模板，结束时清理，不托管整个后端目录。
来源素材保持原始比例，短素材结束后保留末帧，不循环制造新的演示过程。
字幕保留实测时间，不按字数分配播放时间。

输出仍为 `video.mp4`、`poster.png`、`audio.m4a`、`subtitles.srt` 等现有文件。
Node 先写私有 `render-raw-result.json`；后端混音和真实成片检测全部通过后，才原子写出 `render-result.json` 并进入审核。
结果中的 `renderer=hyperframes` 标识实际引擎；进度只反映引擎提供的真实信息，不制造帧计数。

## 验证和部署

```powershell
cd website/skill-finder/backend
uv run python -m ruff check .
uv run python -m pytest -q

cd ../frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
```

数据库集成测试仍只允许独立测试库。真实媒体验收需检查 H.264/yuv420p/AAC、1080×1920、30 FPS、48 kHz 双声道、
整片响度与峰值、音视频时长，以及字幕和素材的实际呈现。
比较两个引擎时应使用相同口播、来源素材和字幕；换引擎不代表事实和制作风格自动合格。

`deploy/Dockerfile` 新增 HyperFrames Node 构建阶段，镜像同时保留 Remotion 回退依赖，运行时复用系统 Chromium 和 FFmpeg。
从微服务目录执行 `docker build -f deploy/Dockerfile -t skill-finder:hyperframes .`；`.dockerignore` 排除密钥、运行数据和宿主机依赖。
现有持久卷覆盖两套模板数据，无需新服务端口。配置 `DAILY_VIDEO_RENDERER=hyperframes` 后再重建、重启目标容器。
本次代码接入不自动部署到远程服务器，也不变更定时任务或发布批准。
本机未安装 Docker，本次未执行镜像构建；发布前仍需在目标部署环境验证镜像启动与完整渲染。

本地验收（2026-10-26）：使用同一份已有口播、来源视频和实测字幕完成 26.77 秒对比样片，
输出 1080×1920 / 30 FPS、H.264/yuv420p、AAC 48 kHz 双声道；编码后响度 −16.02 LUFS、真峰值 −2.90 dBTP。
真实 Chromium 验证了沙箱预览的字体加载、播放暂停、拖动时间轴、演示切换，以及隔离目录中的模板保存与恢复。

官方资料：[HyperFrames](https://github.com/heygen-com/hyperframes)、[producer API](https://github.com/heygen-com/hyperframes/tree/main/packages/producer)。
