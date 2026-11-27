"""日报与独立 Node 渲染器的边界：只传本地媒体和结构化清单。

`prepare` 固化项目素材、合成配音、对齐字幕并写出 `render-manifest.json`；
`invoke_renderer` 调用 `video-renderer/scripts/render.mjs`；`render` 在付费合成前
检查 Node 与 `node_modules/remotion`，再交给 `rendering.finish_render` 统一验收。

外部二进制：node（Remotion 渲染）、ffmpeg 与 ffprobe（素材探测、母带、成片验收）。
素材只从 `DAILY_ASSETS_DIR` 的 manifest 读取，禁止任意 URL 抓取和目录穿越；环境
缺失或验收失败直接抛 `RuntimeError`，不会自动切换到 HyperFrames。
"""
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
    """把某个项目在 `DAILY_ASSETS_DIR` 的固化素材复制进任务目录。

    只认 `owner--repo.json` 这份 manifest，禁止按任意 URL 抓取，也禁止目录穿越；
    来源必须是 HTTPS，文件必须落在资产目录内。

    Args:
        scene: 分镜字典，用 `heading`（`owner/repo`）定位 manifest。
        work: 该分镜的工作目录，素材复制为 `source<后缀>`。
        assets_dir: 覆盖默认素材目录，样片与测试用。

    Returns:
        渲染器需要的 `{"src", "kind", "source"}`；视频额外带 `durationInFrames`。
        没有 manifest 时返回 `None`，表示该分镜不使用演示素材。

    Raises:
        ValueError: 来源不是 HTTPS、文件跑出资产目录、格式不支持或视频时长非法。
    """
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
    """固化素材、合成配音、对齐字幕并写出渲染清单。

    顺序很重要：先校验 `DAILY_REQUIRE_DEMO_ASSETS` 并逐个复制素材，再固化配乐，
    最后才逐段合成付费人声，避免坏素材或未授权的配乐在花钱之后才被发现。

    Args:
        scenes: `compose` 产出的分镜列表。
        day: `YYYY-MM-DD`，写入清单供渲染器展示。
        directory: 本期任务目录。
        assets_dir: 覆盖默认素材目录。
        template_selection: 返回 `(工程目录, 主题, revision)` 的可调用对象；默认取
            当前激活的 Remotion 版本。

    Returns:
        同时写入 `render-manifest.json` 的字典：分镜（含音频相对路径、字幕、帧长、
        母带参数）、主题、模板 revision、配乐与字体文件名。

    Raises:
        RuntimeError: 缺少要求的演示素材、配音失败、时长非法或字幕时间越界。
    """
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
    """用 Remotion 渲染当前任务目录：复用依赖检查和受限进程调用，演示片不调用 TTS。

    Args:
        directory: 含 `render-manifest.json` 的任务目录。
        demo: 透传 `--demo`，只渲染演示片，不调用 TTS。
        check: 透传 `--check`，只渲染一帧做校验，超时 120 秒。
        template_project: 显式指定的模板工程；默认取当前激活版本。

    Raises:
        RuntimeError: Node 缺失、`node_modules/remotion` 未安装、超时或非零退出。
    """
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
    """Remotion 渲染入口：先检查 Node 与依赖，再校验 FFmpeg 工具。

    依赖检查放在 `ensure_tools` 与 `prepare` 之前，因此配置错误不会消耗配音额度；
    失败不自动切换到 HyperFrames。

    Returns:
        成片时长，单位秒。
    """
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
