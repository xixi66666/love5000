# 自然背景来源

背景为摄影者 **Yaroslav Shuraev** 的森林湖泊晨雾航拍 [Foggy Day in a Lake in the Forest](https://www.pexels.com/video/foggy-day-in-a-lake-in-the-forest-5563080/)，Pexels 素材编号 `5563080`，页面标注上传于2020-10-09。采用实拍风景，画面没有增加合成景物。

原始视频：[Pexels 官方4K MP4](https://videos.pexels.com/video-files/5563080/5563080-uhd_3840_2160_24fps.mp4)。核验为H.264、3840×2160、24fps、34.791667秒、106,589,091字节。

- `motion-background.mp4`：4K原片以FFmpeg Lanczos缩至1920×1080，H.264（CRF 20、yuv420p）、24fps、34.791667秒、无音轨、23,031,119字节（约23MB）；前置播放索引，保留整段镜头，浏览器循环播放。
- `motion-background.jpg`：网页视频第3秒的高清静态海报，1920×1080、87,265字节（约87KB）。
- 运行时全部同源读取，无外部媒体请求；暂停、后台停播及减少动画偏好由 `../motion.js` 管理。替换视频、海报时同步更新HTML/CSS中的资源版本，避免旧背景缓存。
- 4K原片和制作中间文件只在被Git忽略的 `.runtime/`，不作为页面资源或提交。

来源与授权核对时间：2026-10-14。[Pexels License](https://www.pexels.com/license/)允许免费下载、修改，并在网站或应用中使用；不出售未修改素材、不暗示摄影者背书、不将其作为素材平台再分发。本项目仅将加工视频用于个人Agent网页背景，保留作者与来源记录。
