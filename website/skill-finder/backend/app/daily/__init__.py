"""Skill Finder 每日 AI 趋势日报与竖屏视频的编排层。

模块按职责拆分：`pipeline` 选题、写稿并串起整条流水线；`speech` 与 `audio` 负责
真实配音、实测字幕和 FFmpeg 母带；`remotion`、`hyperframes`、`rendering` 对接外部
Node 渲染器并统一验收；`progress` 与 `store` 记录真实进度与人工批准凭据；`assets`
与 `console` 提供素材接收和操作台状态；`publisher`、`douyin_login` 只在人工批准
之后触达抖音。

运行数据只写入 `settings.daily_reports_dir`（默认 `data/daily-reports`）与
`settings.daily_assets_dir`（默认 `data/video-assets`），属于私有内容，不写日志、
不回响应。任务目录里的 `workflow.json` 只记录实际发生的步骤，`render-progress.json`
只记录渲染器自己报告的真实帧数。

外部命令：node（Remotion / HyperFrames 渲染）、ffmpeg 与 ffprobe（母带和成片验收）、
可选的 openclaw（QQ 通知）。任一步失败都会把报告停在失败状态并向上抛出，不伪造
成功、不估算进度，也不在两种视频引擎之间自动切换。
"""
