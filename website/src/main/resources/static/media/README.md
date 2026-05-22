# 首页电影级背景素材

首页会优先加载以下本地素材：

```text
hero-blackhole.webm
hero-blackhole.mp4
hero-blackhole-poster.webp
```

没有视频素材时，页面会自动使用 Canvas 黑洞作为兜底背景，不会空白。

## 使用 Sora 生成

先在同一个 PowerShell 会话中设置 OpenAI API Key：

```powershell
$env:OPENAI_API_KEY="your-new-key"
```

然后从仓库根目录运行：

```powershell
.\scripts\generate-sora-blackhole.ps1
```

脚本会调用 OpenAI Video API，默认使用：

```text
model: sora-2-pro
size: 1280x720
seconds: 8
output: website/src/main/resources/static/media/hero-blackhole.mp4
```

如果本机有 `ffmpeg`，脚本还会自动导出：

```text
hero-blackhole-poster.webp
hero-blackhole.webm
```

## 视觉方向

生成提示词会要求原创黑洞视频背景：

- 巨大暗色事件视界
- 横向白金色吸积盘
- 冷蓝黑深空
- 细密星场和缓慢轨道尘埃
- 无文字、无人物、无 logo、无 UI
- 避免复刻任何电影画面

建议控制单个视频文件体积在 5MB 到 12MB 以内。
