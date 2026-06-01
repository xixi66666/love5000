# AI 原创国风动漫 MVP 设计

## 目标

第一阶段做一个本地 Python 命令行工具，用于跑通 AI 原创国风动漫短片的前期制作链路。工具不直接调用 AI 生成接口，只管理本地素材、检查素材完整性、生成字幕、自动合成 9:16 预览视频，并实验性输出剪映精修辅助文件。

## 样片方向

- 类型：国风玄幻 / 妖怪 / 修仙
- 主角：冷艳杀伐型妖刀少女
- 时长：15 秒
- 画幅：9:16 竖屏
- 结构：4 个镜头
- 表达：旁白驱动
- 剧情：雨夜里妖刀少女拔刀救下路人，最后路人发现她才是真正的妖怪
- 结尾：路人低头道谢，再抬头时发现少女的影子不是人形

## 制作链路

```text
原创想法
  -> 剧本和分镜
  -> 关键帧图片
  -> 图生视频片段
  -> AI 配音和 BGM
  -> Python 工具检查素材
  -> 自动生成字幕
  -> 自动合成 preview.mp4
  -> 输出剪映精修辅助文件
```

## 项目目录

默认项目根目录：

```text
D:\Code\video\anime_projects
```

单个项目目录：

```text
anime_projects\
  001_雨夜妖刀少女\
    project.json
    storyboard.json
    script\
      narration.txt
      title.txt
    assets\
      keyframes\
        shot_01.png
        shot_02.png
        shot_03.png
        shot_04.png
      videos\
        shot_01.mp4
        shot_02.mp4
        shot_03.mp4
        shot_04.mp4
      audio\
        voice.mp3
        bgm.mp3
    output\
      subtitles.srt
      preview.mp4
      production_report.md
      manual_cutting_guide.md
      jianying_draft\
```

## CLI 命令

```bash
python anime_cli.py init "001_雨夜妖刀少女"
python anime_cli.py check "001_雨夜妖刀少女"
python anime_cli.py render "001_雨夜妖刀少女"
python anime_cli.py draft "001_雨夜妖刀少女"
```

- `init`：创建项目目录和模板文件。
- `check`：检查分镜配置、镜头视频、旁白、BGM 是否齐全。
- `render`：生成字幕并调用 FFmpeg 合成 `output/preview.mp4`。
- `draft`：输出剪映精修辅助文件；剪映草稿能力为实验性增强，不阻塞主流程。

## 自动剪辑能力

第一版预览视频包含：

- 4 个镜头按顺序拼接
- 统一转成 1080x1920 竖屏
- 片头标题
- 简单淡入淡出
- 旁白音轨
- BGM 音轨
- 字幕烧录
- 输出 MP4

## 剪映草稿边界

剪映草稿生成为实验模块。第一版优先输出稳定的 `manual_cutting_guide.md` 和素材清单；如果后续确认本机剪映草稿格式，可以继续适配真正的草稿目录。主流程不能依赖剪映草稿成功。

## 第一支样片分镜

1. 雨夜危机，3.5 秒：路人被黑影逼到巷口。
2. 少女出现，3.5 秒：红黑衣袍的妖刀少女从雨夜中走来。
3. 拔刀救人，4 秒：少女拔刀斩碎黑影。
4. 影子反转，4 秒：路人道谢后抬头，发现少女身后的影子不是人形。

## 风险

- 剪映草稿格式可能受版本影响，第一版不保证直接导入。
- 图生视频质量不可控，需要多次生成和人工筛选。
- 角色一致性第一版靠角色设定、关键帧和提示词管理，不接入 LoRA 或模型训练。
- 第一版不做自动 AI 文本、图片、视频、配音生成，也不做自动发布。
