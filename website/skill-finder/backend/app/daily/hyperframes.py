"""HyperFrames 渲染引擎适配层（当前默认引擎）。

只替换画面编排：素材固化、配音、实测字幕、混音与成片验收仍复用
`remotion.prepare` 与 `audio.master_video`，因此两种引擎的验收口径完全一致。

外部依赖：Node.js 22+ 执行 `hyperframes-renderer/scripts/render.mjs`，
`node_modules/@hyperframes/producer` 与 `@hyperframes/engine` 必须已安装，浏览器由
`HYPERFRAMES_BROWSER_EXECUTABLE` 或系统 Chrome/Chromium 提供，并发度来自
`HYPERFRAMES_CONCURRENCY`（1–8）。环境缺失时直接抛 `RuntimeError`，不会静默改用
Remotion。
"""
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
    """配音前确认浏览器可用，与 Node 渲染器使用相同的搜索顺序。

    显式配置 `HYPERFRAMES_BROWSER_EXECUTABLE` 时只认这个文件，不再回退系统浏览器；
    未配置时依次查找 chromium、chromium-browser、google-chrome、chrome。

    Raises:
        RuntimeError: 找不到可执行文件，直接失败而不是换引擎。
    """
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
    """检查 Node、HyperFrames 依赖与浏览器是否齐备。

    Returns:
        解析后的 node 可执行文件路径，供 `invoke_renderer` 复用。

    Raises:
        RuntimeError: Node 缺失、`@hyperframes` 依赖未安装或浏览器不可用。这里
            不检查 Remotion 依赖，也不在缺失时静默改用其他引擎。
    """
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
    """用 Node 渲染器渲染当前任务目录。

    Args:
        directory: 含 `render-manifest.json` 的任务目录。
        demo: 透传 `--demo`，只生成引擎演示片，不走配音。
        check: 透传 `--check`，只渲染一帧做校验，超时收紧到 120 秒。
        template_project: 显式指定的模板工程；默认取当前激活版本。

    Raises:
        RuntimeError: 运行环境缺失、渲染超时或 Node 非零退出，错误信息已脱敏。
    """
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
    """HyperFrames 渲染入口：先校验运行时与音频工具，再准备素材与配音。

    校验顺序保证配置错误在任何付费 TTS 之前暴露：`ensure_runtime`（引擎、依赖、
    浏览器）先于 `ensure_tools`（ffmpeg 滤镜），两者都先于 `prepare` 合成语音。

    Returns:
        成片时长，单位秒，取自统一验收后的 `render-result.json`。
    """
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
