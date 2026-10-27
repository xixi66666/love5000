# HyperFrames 渲染器

Skill Finder 的内部 HTML + GSAP 视频工程，使用官方 HyperFrames producer/engine API。
复用后端提供的素材、配音和实测字幕，不新增服务或端口。

需要 Node.js 22+、FFmpeg/ffprobe 和已安装的 Chromium/Chrome。
依赖锁定为 HyperFrames 0.8.186、GSAP 3.13.0、linkedom 0.18.12。

```powershell
npm ci
npm run check
npm test
```

后端默认使用 `DAILY_VIDEO_RENDERER=hyperframes`，Remotion 保留为备用项（`DAILY_VIDEO_RENDERER=remotion`）；按需设置浏览器完整路径
`HYPERFRAMES_BROWSER_EXECUTABLE`。默认并发 `HYPERFRAMES_CONCURRENCY=1`，支持 1–8。
Node、FFmpeg 和 ffprobe 使用原有 `DAILY_*_COMMAND` 配置。
完整配置、模板 API 和部署说明见 [接入文档](../docs/hyperframes-integration.md)。

## 渲染与输出

```powershell
node scripts/render.mjs /absolute/report/render-manifest.json
# 仅渲染校验帧，不调用配音
node scripts/render.mjs /absolute/report/render-manifest.json --check
# 自带九秒演示，生成 demo.mp4；附静音音轨
node scripts/render.mjs /absolute/output/render-manifest.json --demo
```

直接运行脚本时，媒体工具使用 `HYPERFRAMES_FFMPEG_COMMAND` / `HYPERFRAMES_FFPROBE_COMMAND`，
未设置时从 PATH 解析。后端会把 `DAILY_*_COMMAND` 显式传入这两个变量。

生产清单包含 `day`、`scenes`、可选 `font`、`theme`、`template_revision`；每个场景有
`heading`、`label`、`summary`、`narration`、`audio`、`durationInFrames`、`captions` 及可选 `asset`。
字幕 `start/end` 为场景内真实秒数；所有媒体路径必须位于本期目录内，素材注明 HTTPS 来源。
视频素材只播放一次，较短时保留末帧。

渲染先写 `video.mp4`、`poster.png`、`render-progress.json` 和 `render-raw-result.json`。
后端执行音频母带及实际媒体验收，通过后才写 `render-result.json`。
`.hyperframes-project-*` 是本次任务创建的临时隔离目录，只复制清单中的媒体，结束时清理。

## 模板编辑

操作台可编辑 `src/template.html` 和 `src/demo.html`，默认主题是 `src/template-defaults.json`。
模板通过占位符接收内容，作者动画使用暂停的 GSAP 时间线并注册到 `window.__timelines.daily`。
仅允许本地 GSAP 和固化媒体，禁止远程脚本、CSS 导入及额外 iframe。

`scripts/build-editor.mjs` 将模板动画编译到外部 `app.js`，预览无需 eval。
父页面发送 `{kind: 'sf-template-props', props, demo}`，接收
`sf-template-ready` / `sf-template-error`。预览运行在仅有 `allow-scripts` 权限的沙箱 iframe，
支持播放、暂停和逐帧时间轴。保存前会调用官方引擎实际渲染一帧。

测试覆盖真实模板编译、错误定位、字幕时间边界、内容转义、媒体路径隔离及资源限制。
