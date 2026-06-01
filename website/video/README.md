# AI 原创动漫短片自动生成工具

这是一个本地 Python 命令行工具和 Web 工作台，用于从一句主题自动生成国风动漫动态分镜短片。

当前能力：

```text
主题输入
  -> AI 生成标题、旁白、4 镜头分镜、图片提示词
  -> AI 生成 4 张关键帧图片
  -> 尝试 AI 配音
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

如果以后扩展更多图片、视频、平台 SDK，再追加依赖。

## 二、配置文件

复制模板：

```bash
copy config.example.json config.local.json
```

然后编辑：

```text
config.local.json
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
- `tts_model`：用于生成旁白配音。
- `tts_voice`：TTS 音色。
- `default_bgm`：默认背景音乐路径。

安全要求：

```text
config.local.json 不要提交到 Git
不要把 API Key 写进 README、代码、日志或测试文件
```

本项目 `.gitignore` 已忽略：

```text
config.local.json
```

## 三、默认 BGM

自动合成需要默认 BGM：

```text
assets/default_bgm.mp3
```

如果没有自己的 BGM，可以先生成一个占位氛围音：

```bash
python scripts/create_default_bgm.py
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
python anime_cli.py auto "主题" --config D:\Code\Java_Code\love5000\website\video\config.local.json
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

## 六、测试

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

当前测试覆盖：

- 配置读取
- 项目初始化
- 素材检查
- 字幕生成
- OpenAI 兼容接口返回解析
- 图片动态分镜 FFmpeg 命令构建
- 自动生成管线
- 续跑所需的核心行为

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
python scripts/create_default_bgm.py
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

## 八、建议的新机器启动顺序

```bash
python --version
python -m pip --version
python -m pip install --target .vendor imageio-ffmpeg
copy config.example.json config.local.json
python scripts/create_default_bgm.py
python -m unittest discover -s tests -v
python anime_cli.py auto "雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪"
```

然后查看：

```text
anime_projects/最新项目/output/final.mp4
```

