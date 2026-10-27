"""HyperFrames 只替换画面编排，共享素材、配音、字幕和成片母带。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.core.config import settings
from app.daily.audio import ensure_tools, master_video
from app.daily.media import run
from app.daily.remotion import prepare
from app.daily.rendering import finish_render

RENDERER_DIR = Path(__file__).resolve().parents[3] / "hyperframes-renderer"


def browser_executable() -> str:
    """配音前确认浏览器可用，与 Node 渲染器使用相同的搜索顺序。"""
    if settings.hyperframes_browser_executable:
        browser = Path(settings.hyperframes_browser_executable)
        if browser.is_file():
            return str(browser.resolve())
    else:
        for command in ("chromium", "chromium-browser", "google-chrome", "chrome"):
            if browser := shutil.which(command):
                return browser
    raise RuntimeError("HyperFrames browser missing; configure HYPERFRAMES_BROWSER_EXECUTABLE")


def ensure_runtime() -> str:
    """不检查 Remotion 依赖，也不在缺失时静默改用其他引擎。"""
    node = shutil.which(settings.daily_node_command)
    if not node:
        raise RuntimeError("HyperFrames requires Node.js 22+; configure DAILY_NODE_COMMAND")
    if not all((RENDERER_DIR / "node_modules/@hyperframes" / package / "package.json").is_file()
               for package in ("producer", "engine")):
        raise RuntimeError("HyperFrames dependencies missing: run npm ci in hyperframes-renderer")
    browser_executable()
    return node


def invoke_renderer(directory: Path, *, demo: bool = False, check: bool = False,
                    template_project: Path | None = None) -> None:
    directory = directory.resolve()
    node = ensure_runtime()
    from app.daily.templates import selection

    project = template_project or selection("hyperframes")[0]
    environment = os.environ.copy()
    environment["HYPERFRAMES_TEMPLATE_DIR"] = str(project)
    environment["HYPERFRAMES_CONCURRENCY"] = str(settings.hyperframes_concurrency)
    environment["HYPERFRAMES_FFMPEG_COMMAND"] = settings.daily_ffmpeg_command
    environment["HYPERFRAMES_FFPROBE_COMMAND"] = settings.daily_ffprobe_command
    environment["HYPERFRAMES_BROWSER_EXECUTABLE"] = browser_executable()
    command = [node, str(RENDERER_DIR / "scripts/render.mjs"), str(directory / "render-manifest.json")]
    if demo:
        command.append("--demo")
    if check:
        command.append("--check")
    run(command, cwd=RENDERER_DIR, timeout=120 if check else settings.daily_render_timeout_seconds,
        env=environment)


def render(scenes: list[dict], day: str, directory: Path, assets_dir: Path | None = None) -> float:
    directory = directory.resolve()
    # 付费配音前校验所选引擎与媒体工具，配置错误直接报错。
    ensure_runtime()
    ensure_tools()
    from app.daily.templates import selection

    selected = selection("hyperframes")
    manifest = prepare(scenes, day, directory, assets_dir, template_selection=lambda: selected)
    return finish_render(directory, manifest,
                         invoke=lambda target: invoke_renderer(target, template_project=selected[0]),
                         master=master_video, engine="hyperframes")
