# 首页电影级背景素材

首页会优先加载以下本地素材：

```text
hero-blackhole.webm
hero-blackhole.mp4
hero-blackhole-poster.webp
```

当前页面已经内置 Canvas 兜底背景。没有视频素材时，页面不会空白；生成视频后把文件放到本目录即可自动启用。

推荐生成模型：

```text
model: sora-2-pro
size: 1280x720
seconds: 8
```

推荐提示词：

```text
A cinematic seamless looping hero background for a premium AI technology website. A massive black hole-like ink vortex across the upper half of the frame, dark cosmic background, extremely fine blue-white orbital hairlines, subtle luminous dust, fluid ink turbulence in water, restrained glow, deep black center, high contrast, elegant minimal futuristic atmosphere, no text, no logo, no people, no UI, 16:9, production quality, slow motion, seamless loop feeling.
```

生成后建议：

1. 下载 MP4 作为 `hero-blackhole.mp4`。
2. 转码 WebM 为 `hero-blackhole.webm`，优先供 Chromium 浏览器加载。
3. 导出首帧或最佳帧为 `hero-blackhole-poster.webp`。
4. 控制单个视频文件体积，首页背景建议 5MB 到 12MB 以内。
