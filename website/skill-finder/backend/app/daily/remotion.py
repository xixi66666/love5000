"""日报与独立 Node 渲染器的边界：只传本地媒体和结构化清单。"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import settings
from app.daily.audio import ensure_tools, master_video, normalize_voice, prepare_music
from app.daily.media import run, timestamp
from app.daily.progress import current
from app.daily.speech import synthesize

RENDERER_DIR = Path(__file__).resolve().parents[3] / "video-renderer"


def asset_for(scene: dict, work: Path, assets_dir: Path | None = None) -> dict | None:
    """素材由本地 manifest 显式提供，禁止任意 URL 抓取与目录穿越。"""
    heading = scene["heading"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", heading):
        return None
    root = Path(assets_dir or settings.daily_assets_dir).resolve()
    manifest = root / (heading.replace("/", "--") + ".json")
    if not manifest.is_file():
        return None
    asset = json.loads(manifest.read_text(encoding="utf-8"))
    source = asset.get("source", "")
    if not isinstance(source, str) or len(source) > 500 or urlsplit(source).scheme != "https":
        raise ValueError("Video asset needs an HTTPS source attribution")
    original = (root / asset["file"]).resolve()
    if not original.is_relative_to(root) or not original.is_file():
        raise ValueError("Video asset must be a file inside DAILY_ASSETS_DIR")
    suffix = original.suffix.lower()
    if suffix not in {".mp4", ".png", ".jpg", ".jpeg"}:
        raise ValueError("Unsupported video asset format")
    target = work / ("source" + suffix)
    shutil.copyfile(original, target)
    result = {"src": target.relative_to(work.parent).as_posix(),
              "kind": "video" if suffix == ".mp4" else "image", "source": source}
    if suffix == ".mp4":
        probe = json.loads(run([settings.daily_ffprobe_command, "-v", "quiet", "-show_format",
                               "-of", "json", str(target)]))
        duration = float(probe["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid source video duration")
        result["durationInFrames"] = max(1, math.floor(duration * 30))
    return result


def prepare(scenes: list[dict], day: str, directory: Path, assets_dir: Path | None = None, *,
            template_selection: Callable[[], tuple[Path, dict, str]] | None = None) -> dict:
    progress = current()
    if settings.daily_require_demo_assets:
        missing = [scene["heading"] for scene in scenes
                   if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", scene["heading"])
                   and not (Path(assets_dir or settings.daily_assets_dir)
                            / (scene["heading"].replace("/", "--") + ".json")).is_file()]
        if missing:
            raise RuntimeError("Verified demo assets required in DAILY_ASSETS_DIR: " + ", ".join(missing))
    assets = []
    # 所有素材先完成复制与探测，避免合成多段付费人声后才发现坏素材。
    for i, scene in enumerate(scenes):
        work = directory / f"scene-{i:02}"
        work.mkdir(exist_ok=True)
        assets.append(asset_for(scene, work, assets_dir))
    music = prepare_music(directory)
    if progress:
        progress.finish("assets", f"已检查 {len(scenes)} 个分镜，项目素材已固化。")
        progress.stage("voice")["total"] = len(scenes)
        progress.stage("captions")["total"] = len(scenes)
    prepared, all_srt, offset, next_index = [], [], 0.0, 1
    for i, scene in enumerate(scenes):
        work = directory / f"scene-{i:02}"
        work.mkdir(exist_ok=True)
        audio, captions = synthesize(scene["narration"], work)
        normalized = work / "voice-normalized.wav"
        normalization = normalize_voice(audio, normalized)
        audio = normalized
        probe = json.loads(run([settings.daily_ffprobe_command, "-v", "quiet", "-show_format",
                                "-of", "json", str(audio)]))
        duration = float(probe["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0 or duration > 600:
            raise RuntimeError("Invalid narration duration")
        for cue in captions:
            cue["end"] = min(cue["end"], duration)
            if cue["end"] <= cue["start"]:
                raise RuntimeError("Caption timing exceeds narration duration")
            all_srt.append(f"{next_index}\n{timestamp(offset + cue['start'])} --> "
                           f"{timestamp(offset + cue['end'])}\n{cue['text']}\n")
            next_index += 1
        frames = math.ceil(duration * 30)
        # 与实际帧长保持同一时间轴，避免多段音频累计偏移。
        offset += frames / 30
        item = {**scene, "audio": audio.relative_to(directory).as_posix(),
                "captions": captions, "durationInFrames": frames, "audio_mastering": normalization}
        asset = assets[i]
        if asset:
            item["asset"] = asset
        prepared.append(item)
    from app.daily.templates import selection

    _, theme, revision = (template_selection or (lambda: selection("remotion")))()
    payload = {"day": day, "scenes": prepared, "theme": theme, "template_revision": revision}
    if music:
        payload["music"] = music
    from app.daily.media import font

    face = font(30)
    font_file = Path(face.path)
    target_font = directory / ("font" + font_file.suffix)
    shutil.copyfile(font_file, target_font)
    payload["font"] = target_font.name
    (directory / "subtitles.srt").write_text("\n".join(all_srt), encoding="utf-8")
    (directory / "render-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def invoke_renderer(directory: Path, *, demo: bool = False, check: bool = False,
                    template_project: Path | None = None) -> None:
    """复用依赖检查和受限进程调用；演示片不调用 TTS。"""
    node = shutil.which(settings.daily_node_command)
    if not node:
        raise RuntimeError("Remotion requires Node.js 22+; configure DAILY_NODE_COMMAND")
    if not (RENDERER_DIR / "node_modules/remotion/package.json").is_file():
        raise RuntimeError("Remotion dependencies missing: run pnpm install in video-renderer")
    environment = os.environ.copy()
    environment["REMOTION_CONCURRENCY"] = str(settings.remotion_concurrency)
    from app.daily.templates import selection

    project = template_project or selection("remotion")[0]
    environment["REMOTION_TEMPLATE_DIR"] = str(project)
    if settings.remotion_browser_executable:
        environment["REMOTION_BROWSER_EXECUTABLE"] = settings.remotion_browser_executable
    command = [node, str(RENDERER_DIR / "scripts/render.mjs"), str(directory / "render-manifest.json")]
    if demo:
        command.append("--demo")
    if check:
        command.append("--check")
    run(command,
        cwd=RENDERER_DIR, timeout=120 if check else settings.daily_render_timeout_seconds, env=environment)


def render(scenes: list[dict], day: str, directory: Path, assets_dir: Path | None = None) -> float:
    directory = directory.resolve()
    # 在付费合成前确认本地运行依赖已准备好。
    if not shutil.which(settings.daily_node_command):
        raise RuntimeError("Remotion requires Node.js 22+; configure DAILY_NODE_COMMAND")
    if not (RENDERER_DIR / "node_modules/remotion/package.json").is_file():
        raise RuntimeError("Remotion dependencies missing: run pnpm install in video-renderer")
    ensure_tools()
    manifest = prepare(scenes, day, directory, assets_dir)
    from app.daily.rendering import finish_render

    return finish_render(directory, manifest, invoke=invoke_renderer, master=master_video,
                         engine="remotion")
