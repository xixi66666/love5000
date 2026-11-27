"""无数据库、无发布动作，使用当前显式选择的视频引擎制作样片。

`generate_sample` 在 `video-samples/<时间戳>/` 下用固定演示分镜渲染一条短片，供
验收模板、配音与字幕链路；样片文案明确声明“非日榜”，不冒充当天 Trending 结果。
`legacy` 配置直接报错，不会静默换成另一个引擎。

外部命令：node、ffmpeg、ffprobe，均经所选引擎的适配层调用；失败向上抛出，样片目录
保留现场供排查。
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.daily import store


def renderer():
    """按当前配置返回选中的引擎模块。

    Raises:
        RuntimeError: 配置为 legacy 时没有样片能力，显式报错而不是换引擎。
    """
    if settings.daily_video_renderer == "hyperframes":
        from app.daily import hyperframes

        return hyperframes
    if settings.daily_video_renderer == "remotion":
        from app.daily import remotion

        return remotion
    raise RuntimeError("Engine samples require DAILY_VIDEO_RENDERER=remotion or hyperframes")


def invoke_renderer(*args, **kwargs):
    """把引擎调用转发给当前配置的引擎，用于生成演示片。"""
    return renderer().invoke_renderer(*args, **kwargs)


def render(*args, **kwargs):
    """把整片渲染转发给当前配置的引擎，供样片使用。"""
    return renderer().render(*args, **kwargs)


def generate_sample() -> dict:
    """用固定演示分镜渲染一条样片，供验收模板、配音与字幕链路。

    样片落在 `video-samples/<时间戳>/`，分镜文案明确声明不代表当天榜单；先用
    `invoke_renderer(..., demo=True)` 生成引擎自带演示素材并写 manifest，再走与
    正式成片相同的 `render` 流程（含母带与验收）。

    Returns:
        含样片目录、时长、状态与引擎标识的字典。

    Raises:
        RuntimeError: 当前引擎为 legacy，或渲染、验收失败。
    """
    engine = settings.daily_video_renderer
    renderer()  # legacy 模式不静默制作另一引擎的样片。
    hyperframes = engine == "hyperframes"
    label = "HyperFrames" if hyperframes else "Remotion"
    project = "heygen-com/hyperframes" if hyperframes else "remotion-dev/remotion"
    # 只陈述本地实际展示的能力，样片数据不冒充当天 Trending 榜单。
    scenes = [
        {"label": "TOOL CHECK", "heading": "每天的视频，交给模板。",
         "summary": f"这是一条 {label} 接入样片。演示本地模板渲染，不代表当天榜单。",
         "narration": "每天的视频，都要重新剪？先看这个工具。"},
        {"label": label.upper(), "heading": project,
         "summary": ("HTML、CSS 和 GSAP 写画面。" if hyperframes else "React 写画面。")
                    + "JSON 换内容。动画、配音和字幕，按时间轴自动合成。",
         "narration": f"{label}，用代码做视频。标题、图片和配音，交给同一套模板。"
                      "每天换一份数据，就能生成新的成片。画面里的动画，就是它实际渲染的效果。"},
        {"label": "YOUR WORKFLOW", "heading": "把重复剪辑，变成一次设计。",
         "summary": "适合内容结构稳定、需要重复制作的视频。模板需要开发，成片仍要审核。",
         "narration": "适合榜单、日报，还有产品介绍。模板需要开发，内容也要核对。"
                      "先做一条样片，再决定要不要用。"},
    ]
    stamp = datetime.now(ZoneInfo(settings.business_timezone)).strftime("%Y%m%d-%H%M%S")
    directory = store.root().parent / "video-samples" / stamp
    directory.mkdir(parents=True)
    # 使用所选引擎实际渲染的动画，不依赖开发机的私有素材库。
    sources = directory / "sample-assets"
    sources.mkdir()
    invoke_renderer(sources, demo=True)
    (sources / (project.replace("/", "--") + ".json")).write_text(json.dumps({
        "file": "demo.mp4", "source": "https://github.com/" + project,
    }), encoding="utf-8")
    duration = render(scenes, "接入样片 · 非日榜", directory, sources)
    return {"directory": str(directory), "duration_seconds": duration, "status": "sample_ready",
            "renderer": engine}
