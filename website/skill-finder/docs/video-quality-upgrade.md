# 一键视频制作质量升级

可切换 HyperFrames 视频引擎已另行接入，详见 [HyperFrames 接入](hyperframes-integration.md)。下述口播、实测字幕与 FFmpeg 母带能力由两套引擎共同使用。

保留 Remotion 4.0.536、FFmpeg/ffprobe 和原 MiMo 配音，继续使用 `/daily-reports` 的一键制作、模板编辑和审核流程。
此次升级作用于后续生成的成片；历史视频与已保存的私有模板版本不被覆盖。

## 画面、口播与字幕

- 默认模板采用标题导入、宽幅演示和资料重点三段编排。短视频不再硬循环，素材结束后保留末帧并标记；横屏演示保持比例。
- 仍采用现有纸白、橙、黑配色，保留主题编辑字段、来源、日期和手机安全区。
- H.264 输出调整为 CRF 18 / medium，1080×1920 / 30 FPS 不变；编码时间和资源消耗可能增加。
- Remotion 与 HyperFrames 均输出 BT.709 有限范围 `yuv420p`，以满足统一的成片检测。
- 口播清理 Markdown、HTML 和 URL 展示语法，不逐项机械念 Star；排名、Star 与来源仍留在画面及日报。
- 日报保留完整简介，单项目口播最多 360 字，只选择完整句，优先保留限制条件。无法安全容纳时提示查看完整来源。
- MiMo 音色和风格配置继续有效。字幕使用实际音轨转写后与原稿对齐；长句尽量在可信词边界拆为 18 字以内。
  一个词没有可确认的内部时间边界时保留完整词，不按字数均分时间，也不伪造逐字高亮。

## 音频与成片检测

人声与整片使用 FFmpeg 双遍响度处理，优先采用线性模式，必要的动态处理会如实记录。
内部目标约 -16 LUFS；整片 PCM 预留 AAC 编码峰值余量，最终交付文件检测真峰值不高于 -1 dBTP。
音轨输出为 48 kHz 双声道 AAC。不会把升采样描述为原始音质提升。

渲染后继续进行混音、响度测量和真实 ffprobe 检测，验证分辨率、帧率、音视频流、起始时间与时长。
完成检测后才进入待审核状态；画面帧数达到 100% 时可能仍在处理音频，页面会显示“正在混音并检测成片”。
检测失败会中止任务。处理结果写入原私有 `render-result.json` 的 `audio_mastering`，不新增公开文件下载接口。

## 可选本地配乐

默认纯人声，无需新增服务账户。可在后端私有环境配置用户有权使用的本地配乐：

```dotenv
DAILY_BGM_FILE=D:/media/licensed-background.wav
DAILY_BGM_SOURCE=https://example.com/your-licensed-source
```

`DAILY_BGM_FILE` 支持 WAV、MP3、M4A、AAC、FLAC、OGG；`DAILY_BGM_SOURCE` 为可追溯 HTTPS 来源，不含用户名、密码、查询参数或片段。
系统只使用本地文件，不下载来源链接。配置的来源与文件在付费配音前验证；缺文件或无效音轨会直接失败。
填写来源不代表自动获得授权，应使用自己的录音或已获授权的素材。

音乐复制到该期目录固化，先降低响度，再通过 sidechaincompress 在人声出现时自动压低，首尾淡入淡出。
`audio.m4a` 与视频内的最终混音一致。删除两项配置即可恢复纯人声。
Docker 部署时文件必须挂载到容器可读路径，不能直接填写宿主机 Windows 路径。

## 运行与验证

原有 Python、Node 22+、渲染器、FFmpeg/ffprobe 和 faster-whisper 环境继续复用，无新增依赖。
本地后端代码更新后重启 5177；前端改动需重新构建 `frontend/dist`。

```powershell
cd website/skill-finder/backend
uv run python -m ruff check .
uv run python -m pytest -q

cd ../video-renderer
pnpm run typecheck
pnpm test

cd ../frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build

cd ../backend
uv run python -m app.daily.cli sample
```

样片输出到 `DAILY_REPORTS_DIR` 同级 `video-samples/<timestamp>/`；样片会调用已配置的配音服务，不创建发布任务。
若已启用私有模板，模板不会自动替换为新默认源码；可在模板编辑器按需合并新 `src/video.tsx` 后预览、保存。
先在手机尺寸检查字幕、演示细节与素材结束处，再用耳机和手机外放试听口播和混音。
自动检测通过只表示技术指标合格，成片风格仍需试听和审看。

参考：[FFmpeg 响度与旁链滤镜](https://ffmpeg.org/ffmpeg-filters.html)、[Remotion 编码选项](https://www.remotion.dev/docs/options/codec)。
