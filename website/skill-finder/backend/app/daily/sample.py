"""无数据库、无发布动作的 Remotion 样片入口。"""
import json
from datetime import datetime

from app.daily import store
from app.daily.remotion import invoke_renderer, render


def generate_sample() -> dict:
    # 只陈述已核实的 Remotion 能力，样片数据不冒充当天 Trending 榜单。
    scenes = [
        {"label": "TOOL CHECK", "heading": "每天的视频，交给模板。",
         "summary": "这是一条 Remotion 接入样片。演示本地模板渲染，不代表当天榜单。",
         "narration": "每天的视频，都要重新剪？先看这个工具。"},
        {"label": "REMOTION", "heading": "remotion-dev/remotion",
         "summary": "React 写画面。JSON 换内容。动画、配音和字幕，按时间轴自动合成。",
         "narration": "Remotion，用代码做视频。标题、图片和配音，交给同一套模板。"
                      "每天换一份数据，就能生成新的成片。画面里的动画，就是它实际渲染的效果。"},
        {"label": "YOUR WORKFLOW", "heading": "把重复剪辑，变成一次设计。",
         "summary": "适合内容结构稳定、需要重复制作的视频。模板需要开发，成片仍要审核。",
         "narration": "适合榜单、日报，还有产品介绍。模板需要开发，内容也要核对。"
                      "先做一条样片，再决定要不要用。"},
    ]
    directory = store.root().parent / "video-samples" / datetime.now().strftime("%Y%m%d-%H%M%S")
    directory.mkdir(parents=True)
    # 使用工程自身实际渲染的动画作 Remotion 演示，不依赖开发机的私有素材库。
    sources = directory / "sample-assets"
    sources.mkdir()
    invoke_renderer(sources, demo=True)
    (sources / "remotion-dev--remotion.json").write_text(json.dumps({
        "file": "demo.mp4", "source": "https://github.com/remotion-dev/remotion",
    }), encoding="utf-8")
    duration = render(scenes, "接入样片 · 非日榜", directory, sources)
    return {"directory": str(directory), "duration_seconds": duration, "status": "sample_ready"}
