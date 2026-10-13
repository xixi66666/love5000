# Pulse 动态背景

素材来自 [MotionSite 背景库](https://www.motionsite.ai/backgrounds) 的 **Pulse**，通过页面公开的 Download 按钮获取。原始下载地址为 `https://strvid.nyc3.cdn.digitaloceanspaces.com/motionitems/backgrounds/clean_Plasma_ring_animation.mp4`。保留来源记录，不将素材标为本项目原创。

- `pulse-ring.mp4`：网页用 H.264 版本，1280×720、24fps、10秒循环，已移除音轨并启用 faststart；约2MB。
- `pulse-ring.jpg`：由视频第0.25秒提取的静态海报；约59KB。

视频由 `motion.js` 在允许动态效果时加载，静音循环播放。顶部按钮可以暂停与恢复，标签页隐藏或背景区域滚出视口时自动暂停；启用 `prefers-reduced-motion` 时只显示海报，不下载视频。播放失败保留海报及 CSS 降级背景。
