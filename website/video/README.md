# AI 原创动漫短片自动生成工具

这是一个本地 Python 命令行工具和 Web 工作台，用于从一句主题自动生成国风动漫动态分镜短片。

当前能力：

```text
主题输入
  -> AI 生成标题、旁白、4 镜头分镜、图片提示词
  -> AI 生成 4 张关键帧图片
  -> 腾讯云或 OpenAI TTS 生成旁白配音
  -> 自动生成字幕
  -> FFmpeg 合成 9:16 动态分镜视频
  -> 输出 output/final.mp4
```

注意：当前是“动态分镜视频”，不是图生视频模型生成的真实角色动作。角色动作目前靠图片推拉镜头实现。

## 一、新机器需要安装什么

### 1. Python

推荐安装 Python 3.11 或更高版本。

下载地址：

```text
https://www.python.org/downloads/
```

安装时建议勾选：

```text
Add python.exe to PATH
```

验证：

```bash
python --version
python -m pip --version
```

### 2. FFmpeg

本项目合成视频需要 FFmpeg。

推荐方式一：项目本地安装，不污染系统环境：

```bash
python -m pip install --target .vendor imageio-ffmpeg
```

程序会自动从下面目录寻找 FFmpeg：

```text
.vendor/imageio_ffmpeg/binaries/
```

推荐方式二：系统安装 FFmpeg。

Windows 可以用 winget：

```bash
winget install --id Gyan.FFmpeg -e
```

安装后验证：

```bash
ffmpeg -version
```

只要方式一或方式二有一个可用即可。

### 3. Python 依赖

当前核心代码主要使用 Python 标准库。为了保证 FFmpeg 可用，建议安装：

```bash
python -m pip install --target .vendor imageio-ffmpeg
```

如果使用腾讯云语音合成旁白，还需要安装腾讯云 TTS SDK：

```bash
python -m pip install --target .vendor tencentcloud-sdk-python-tts
```

如果以后扩展更多图片、视频、平台 SDK，再追加依赖。

## 二、配置文件

复制模板：

```bash
copy config\config.example.json config\config.local.json
```

然后编辑：

```text
config/config.local.json
```

示例：

```json
{
  "openai": {
    "base_url": "https://nimabo.cn",
    "api_key": "请填写你的API_KEY",
    "text_model": "gpt-5.5",
    "image_model": "gpt-image-2",
    "tts_model": "gpt-4o-mini-tts",
    "tts_voice": "alloy"
  },
  "tts": {
    "provider": "tencent"
  },
  "tencent_tts": {
    "secret_id": "请填写你的腾讯云 SecretId",
    "secret_key": "请填写你的腾讯云 SecretKey",
    "region": "ap-guangzhou",
    "voice_type": 101001,
    "primary_language": 1,
    "codec": "mp3",
    "sample_rate": 16000,
    "speed": 0,
    "volume": 5
  },
  "modelscope_video": {
    "api_key": "请填写你的 DashScope API Key",
    "base_url": "https://dashscope.aliyuncs.com/api/v1",
    "model": "wanx2.1-i2v-plus",
    "duration": 5,
    "resolution": "720P",
    "poll_interval_seconds": 5,
    "timeout_seconds": 600
  },
  "assets": {
    "default_bgm": "assets/default_bgm.mp3"
  }
}
```

说明：

- `base_url`：OpenAI 兼容接口地址。代码会自动补 `/v1`。
- `api_key`：你的接口密钥。不要提交到 Git。
- `text_model`：用于生成剧本、分镜、提示词。
- `image_model`：用于生成关键帧图片。
- `tts.provider`：旁白合成服务，支持 `tencent` 或 `openai`。
- `tts_model` / `tts_voice`：当 `tts.provider` 为 `openai` 时使用。
- `tencent_tts.secret_id` / `secret_key`：腾讯云访问密钥，只写入本地 `config/config.local.json`。
- `tencent_tts.region`：腾讯云 TTS 地域，默认 `ap-guangzhou`。
- `tencent_tts.voice_type`：腾讯云音色 ID，可在腾讯云语音合成控制台或文档中选择。
- `tencent_tts.primary_language`：主语言类型，中文填 `1`，英文填 `2`；中文旁白建议显式保留 `1`。
- `tencent_tts.codec`：音频格式，默认 `mp3`，也支持 `wav`、`pcm`。
- `modelscope_video.api_key`：DashScope API Key，用于 ModelScope/Wan 图生视频 API 冒烟测试，只写入本地 `config/config.local.json`。
- `modelscope_video.model`：图生视频模型，默认 `wanx2.1-i2v-plus`。
- `modelscope_video.duration`：生成视频时长，默认 5 秒。
- `modelscope_video.resolution`：生成分辨率，默认 `720P`。
- `image_to_video.enabled`：是否在关键帧之后启用图生视频阶段，默认 `false`，关闭时仍使用当前 FFmpeg 图片动效合成。
- `image_to_video.provider`：图生视频 Provider，支持 `none`、`local_wan`、`dashscope`。
- `local_wan_video.base_url`：本地 Wan/Wan2.2 图生视频服务地址，例如 `http://127.0.0.1:7860`。
- `local_wan_video.endpoint`：本地 Wan 服务生成接口，默认 `/generate`。
- `local_wan_video.timeout_seconds`：本地 Wan 单镜头生成超时时间。
- `default_bgm`：默认背景音乐路径。

安全要求：

```text
config/config.local.json 不要提交到 Git
不要把 API Key 写进 README、代码、日志或测试文件
不要把腾讯云 SecretId / SecretKey 写进 README、代码、日志或测试文件
不要把 DashScope API Key 写进 README、代码、日志或测试文件
```

本项目 `.gitignore` 已忽略：

```text
config.local.json
config/config.local.json
```

## 三、默认 BGM

自动合成需要默认 BGM：

```text
assets/default_bgm.mp3
```

如果没有自己的 BGM，可以先生成一个占位氛围音：

```bash
python python/scripts/create_default_bgm.py
```

生成后会得到：

```text
assets/default_bgm.mp3
```

后续你可以直接替换成真正的音乐文件。

## 四、运行命令

### 1. 一键自动生成

```bash
python anime_cli.py auto "雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪"
```

生成结果会放到：

```text
anime_projects/时间戳_标题/
```

最终视频：

```text
anime_projects/时间戳_标题/output/final.mp4
```

### 2. 续跑已有项目

如果生成过程中中断、超时，或者只生成了一部分图片，可以续跑：

```bash
python anime_cli.py resume-auto "D:\Code\Java_Code\love5000\website\video\anime_projects\20260601_141630_雨刀妖影"
```

续跑会跳过已经存在的关键帧图片和音频，只补缺失素材并重新合成视频。

### 3. 指定配置文件

```bash
python anime_cli.py auto "主题" --config D:\Code\Java_Code\love5000\website\video\config\config.local.json
```

### 4. 指定 BGM

```bash
python anime_cli.py auto "主题" --bgm D:\Music\bgm.mp3
```

### 5. 启动本地 Web 工作台

`video` 作为独立 Python 服务运行，默认端口为 `5176`，不加入父 Maven 工程。

直接启动 `website` 时，Java 侧会自动检查 `http://127.0.0.1:5176/api/health`。如果 `video` 已经可用，会直接复用；如果不可用，会在 `website/video/` 目录下自动执行 `python web_server.py --host 127.0.0.1 --port 5176` 拉起服务。

在 IDEA 中运行 `website` 时，`video` 的启动日志、接口访问日志和错误输出会直接显示在 `website` 的 Run/Terminal 控制台中。`website/src/main/resources/application.yml` 中的 `video.auto-start.log-to-console` 默认为 `true`；如果改为 `false`，日志会写入 `website/video/server.out.log` 和 `website/video/server.err.log`。

```bash
python web_server.py
```

启动后访问：

```text
http://127.0.0.1:5176/
http://127.0.0.1:5176/api/health
```

如果需要指定端口：

```bash
python web_server.py --port 5176
```

## 五、项目输出结构

一次自动生成后的目录大致如下：

```text
anime_projects/
  20260601_141630_雨刀妖影/
    project.json
    storyboard.json
    script/
      title.txt
      narration.txt
      image_prompts.json
    assets/
      keyframes/
        shot_01.png
        shot_02.png
        shot_03.png
        shot_04.png
      audio/
        voice.mp3
        bgm.mp3
    output/
      subtitles.srt
      final.mp4
      generation_report.md
      generation_warnings.md
```

重点文件：

- `storyboard.json`：分镜配置。
- `script/image_prompts.json`：每个镜头的图片提示词。
- `assets/keyframes/shot_*.png`：AI 生成的关键帧。
- `assets/audio/voice.mp3`：AI 配音或静音占位音频。
- `output/subtitles.srt`：字幕文件。
- `output/final.mp4`：最终视频。
- `output/generation_warnings.md`：生成过程中的降级或警告。

## 5.1 本地 Wan/Wan2.2 图生视频扩展

当前项目已经预留本地图生视频扩展位。默认关闭，不影响原来的关键帧合成流程。

开启方式：

```json
{
  "image_to_video": {
    "enabled": true,
    "provider": "local_wan"
  },
  "local_wan_video": {
    "base_url": "http://127.0.0.1:7860",
    "endpoint": "/generate",
    "timeout_seconds": 600
  }
}
```

本地 Wan 服务接口约定：

```text
POST http://127.0.0.1:7860/generate
Content-Type: application/json
```

请求体：

```json
{
  "shot_id": "shot_01",
  "prompt": "镜头缓慢推进，衣袂被风吹动，国风动漫电影感",
  "duration": 5,
  "resolution": "720P",
  "image": "data:image/png;base64,..."
}
```

响应支持三种格式：

```json
{
  "success": true,
  "video_base64": "..."
}
```

或：

```json
{
  "success": true,
  "video_url": "http://127.0.0.1:7860/files/shot_01.mp4"
}
```

也可以直接返回 `video/mp4` 或 `application/octet-stream` 二进制。

启用后自动生成流程会变成：

```text
主题
  -> 生成 storyboard
  -> 生成 assets/keyframes/shot_*.png
  -> 调用本地 Wan 生成 assets/videos/shot_*.mp4
  -> 生成 voice.mp3 / bgm.mp3 / subtitles.srt
  -> FFmpeg 拼接镜头视频并输出 output/final.mp4
```

如果 `image_to_video.enabled=false`，流程保持为：

```text
关键帧图片 + zoompan 动效 + 音频 + 字幕 -> output/final.mp4
```

## 六、验证

当前保留 `tests/` 目录，新增图生视频、任务管理、Web API 或配置逻辑时优先补充 `unittest` 测试：

```bash
python -m unittest discover -s tests -v
```

涉及页面和本地服务联调时再做手动验证：

```bash
python web_server.py
```

然后访问：

```text
http://127.0.0.1:5176/
http://127.0.0.1:5176/api/health
http://127.0.0.1:5176/api/config
```

涉及外部接口时，优先使用 `python/scripts/` 下的 `smoke_*.py` 脚本做单点冒烟验证。

## 七、常见问题

### 1. TTS 返回 404

现象：

```text
TTS 请求失败: HTTP 404 b'404 page not found'
```

原因：

```text
当前 OpenAI 兼容服务可能不支持 /v1/audio/speech 接口。
```

当前处理：

```text
工具会自动生成静音占位 voice.mp3，保证 final.mp4 仍然能合成。
```

后续处理：

```text
换一个支持 TTS 的接口
或手动替换 assets/audio/voice.mp3
然后运行 resume-auto 重新合成
```

### 1.1 腾讯云 TTS SDK 未安装

现象：

```text
缺少腾讯云 TTS SDK，请先安装 tencentcloud-sdk-python-tts
```

解决：

```bash
python -m pip install --target .vendor tencentcloud-sdk-python-tts
```

然后确认 `config/config.local.json` 中：

```json
{
  "tts": {
    "provider": "tencent"
  }
}
```

### 1.2 腾讯云 TTS 密钥缺失

现象：

```text
缺少腾讯云 TTS 配置: tencent_tts.secret_id
```

解决：

```text
在本地 config/config.local.json 填写 tencent_tts.secret_id 和 tencent_tts.secret_key。
不要提交 config/config.local.json，也不要把真实密钥发到聊天、日志或代码仓库。
```

### 2. 找不到 FFmpeg

现象：

```text
'ffmpeg' 不是内部或外部命令
```

解决：

```bash
python -m pip install --target .vendor imageio-ffmpeg
```

或安装系统 FFmpeg：

```bash
winget install --id Gyan.FFmpeg -e
```

### 3. 缺少默认 BGM

现象：

```text
缺少默认 BGM: assets/default_bgm.mp3
```

解决：

```bash
python python/scripts/create_default_bgm.py
```

### 4. 生成图片很慢或命令超时

图片生成接口可能耗时较长。若命令中断，但项目目录里已经有部分图片，可以用：

```bash
python anime_cli.py resume-auto "项目目录绝对路径"
```

### 5. 当前视频为什么不像真正动漫

当前链路是：

```text
AI 关键帧图片 + FFmpeg 推拉镜头 = 动态分镜视频
```

如果要让角色真正动起来，需要后续接入图生视频接口，例如可灵、即梦、Runway 或其他 image-to-video API。

### 6. 先用 ModelScope / DashScope API 测试图生视频

当前主流程还没有接入真正图生视频。可以先用独立冒烟脚本验证 API 是否可用：

```bash
python python/scripts/smoke_modelscope_i2v.py --image-url "https://example.com/shot_01.png" --prompt "镜头缓慢推进，衣袂被风吹动，国风动漫电影感"
```

输出默认写入：

```text
anime_projects/modelscope_i2v_tests/smoke_test.mp4
```

注意：

```text
--image-url 必须是 DashScope 服务可以访问的公网图片 URL。
本地 assets/keyframes/shot_01.png 不能直接传给远端 API。
如果要测试本地关键帧，需要先上传到 OSS、COS、图床或其它可公网访问地址。
```

## 八、建议的新机器启动顺序

```bash
python --version
python -m pip --version
python -m pip install --target .vendor imageio-ffmpeg
copy config\config.example.json config\config.local.json
python python/scripts/create_default_bgm.py
python web_server.py
python anime_cli.py auto "雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪"
```

然后查看：

```text
anime_projects/最新项目/output/final.mp4
```

## 九、文档维护

每次修改 Web API、命令行参数、配置结构、外部 Provider、项目输出结构、测试方式或与 `website` 的自动启动集成时，必须同步更新本 README、`website/video/AGENTS.md`，以及根目录和 `website` 模块的 `AGENTS.md` / `README.md`。

