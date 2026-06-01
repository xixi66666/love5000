from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, List


CommandRunner = Callable[[List[str]], None]


def build_image_storyboard_command(project_dir: Path, storyboard: dict[str, Any]) -> list[str]:
    shots = storyboard["shots"]
    voice = project_dir / "assets" / "audio" / "voice.mp3"
    bgm = project_dir / "assets" / "audio" / "bgm.mp3"
    subtitles = project_dir / "output" / "subtitles.srt"
    final = project_dir / "output" / "final.mp4"

    command = [_resolve_ffmpeg(), "-y"]
    for shot in shots:
        command.extend(
            [
                "-i",
                str(project_dir / "assets" / "keyframes" / f"{shot['id']}.png"),
            ]
        )
    command.extend(["-i", str(voice), "-i", str(bgm)])

    filters: list[str] = []
    labels: list[str] = []
    fps = 30
    for index, shot in enumerate(shots):
        frames = int(round(float(shot["duration"]) * fps))
        label = f"v{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='min(zoom+0.0015,1.08)':d={frames}:s=1080x1920:fps={fps},"
            f"setsar=1[{label}]"
        )

    voice_index = len(shots)
    bgm_index = len(shots) + 1
    total_duration = sum(float(shot["duration"]) for shot in shots)
    fade_out_start = max(total_duration - 0.35, 0)
    filters.extend(
        [
            f"{''.join(labels)}concat=n={len(shots)}:v=1:a=0,"
            f"fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out_start:.2f}:d=0.35,"
            f"subtitles='{_ffmpeg_path(subtitles)}'[v]",
            f"[{voice_index}:a]volume=1.0[a1]",
            f"[{bgm_index}:a]volume=0.18[a2]",
            "[a1][a2]amix=inputs=2:duration=longest[a]",
        ]
    )

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(final),
        ]
    )
    return command


def render_image_storyboard(
    project_dir: Path,
    storyboard: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> Path:
    runner = command_runner or _run_command
    command = build_image_storyboard_command(project_dir, storyboard)
    runner(command)
    return project_dir / "output" / "final.mp4"


def _run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _resolve_ffmpeg() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        vendor = Path(__file__).resolve().parent.parent / ".vendor"
        if vendor.is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return "ffmpeg"


def _ffmpeg_path(path: Path) -> str:
    text = path.resolve().as_posix()
    if len(text) > 1 and text[1] == ":":
        text = text[0] + r"\:" + text[2:]
    return text.replace("'", r"\'")
