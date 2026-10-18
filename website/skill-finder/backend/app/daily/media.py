from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

WIDTH, HEIGHT = 720, 1280
BG, INK, MUTED, GREEN = "#07090c", "#f4f6f8", "#b3bbc8", "#c9fe6e"


def font(size: int):
    candidates = [
        settings.daily_font,
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    raise RuntimeError("Chinese font is missing; set DAILY_FONT")


def wrap(text: str, draw: ImageDraw.ImageDraw, face, width: int) -> list[str]:
    lines, line = [], ""
    for char in text:
        if char == "\n" or (line and draw.textlength(line + char, font=face) > width):
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    return lines


def card(scene: dict, day: str, path: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.text((48, 48), "SKILL FINDER / AI DAILY", font=font(23), fill=GREEN)
    draw.text((48, 94), day + "  ·  GitHub Trending 日榜", font=font(23), fill=MUTED)
    draw.line((48, 154, 672, 154), fill="#30363f", width=2)
    draw.text((42, 176), scene.get("label", "TOP 10"), font=font(126), fill=GREEN)
    y = 370
    for line in wrap(scene["heading"], draw, font(45), 624)[:3]:
        draw.text((48, y), line, font=font(45), fill=INK)
        y += 67
    if scene.get("growth") is not None:
        draw.text((48, y + 25), f"今日 +{scene['growth']:,} Star", font=font(38), fill=GREEN)
        y += 106
    for line in wrap(scene.get("summary", ""), draw, font(30), 624)[:5]:
        draw.text((48, y + 30), line, font=font(30), fill=INK)
        y += 49
    draw.line((48, 1170, 672, 1170), fill="#30363f", width=2)
    draw.text((48, 1193), "来源：GitHub 官方榜单 · AI 配音", font=font(22), fill=MUTED)
    image.save(path)


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 900) -> str:
    result = subprocess.run(args, check=False, cwd=cwd, capture_output=True, timeout=timeout)
    if result.returncode:
        # Do not leak subprocess environments or upstream URLs into public reports.
        raise RuntimeError(f"{Path(args[0]).name} failed (exit {result.returncode})")
    return result.stdout.decode("utf-8", "replace")


async def speech(text: str, target: Path) -> None:
    import edge_tts
    from aiohttp import ClientError
    from edge_tts.exceptions import EdgeTTSException

    for attempt in range(3):
        try:
            communicator = edge_tts.Communicate(text, settings.daily_tts_voice, rate="+8%")
            await asyncio.wait_for(communicator.save(str(target)), timeout=90)
            if target.stat().st_size > 1000:
                return
        except (ClientError, EdgeTTSException, TimeoutError, OSError):
            if attempt == 2:
                raise RuntimeError("Chinese TTS unavailable after 3 attempts") from None
            await asyncio.sleep(2 * (attempt + 1))


def timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def subtitles(text: str, duration: float, offset: float = 0, index: int = 1) -> tuple[str, int]:
    chunks = [piece for piece in re.split(r"(?<=[，。！？；])", text) if piece.strip()]
    chunks = [chunk[i:i + 23] for chunk in chunks for i in range(0, len(chunk), 23)]
    total = sum(map(len, chunks)) or 1
    current, result = offset, []
    for chunk in chunks:
        end = current + duration * len(chunk) / total
        result.append(f"{index}\n{timestamp(current)} --> {timestamp(end)}\n{chunk}\n")
        current, index = end, index + 1
    return "\n".join(result), index


def render(scenes: list[dict], day: str, directory: Path) -> float:
    subtitles_all, offset, next_index = [], 0.0, 1
    for i, scene in enumerate(scenes):
        work = directory / f"scene-{i:02}"
        work.mkdir(exist_ok=True)
        card(scene, day, work / "card.png")
        asyncio.run(speech(scene["narration"], work / "voice.mp3"))
        probe = json.loads(run([
            "ffprobe", "-v", "quiet", "-show_format", "-of", "json", str(work / "voice.mp3"),
        ]))
        duration = float(probe["format"]["duration"])
        srt, _ = subtitles(scene["narration"], duration)
        (work / "captions.srt").write_text(srt, encoding="utf-8")
        full_srt, next_index = subtitles(scene["narration"], duration, offset, next_index)
        subtitles_all.append(full_srt)
        offset += duration
        run([
            "ffmpeg", "-y", "-v", "error", "-threads", "1", "-loop", "1", "-framerate", "15",
            "-i", "card.png", "-i", "voice.mp3", "-vf",
            ("fade=t=in:st=0:d=0.25,subtitles=captions.srt:"
            "force_style='FontName=Noto Sans CJK SC,FontSize=16,MarginV=65,"
             "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'"),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-threads", "1",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-t", str(duration), "-movflags", "+faststart", "clip.mp4",
        ], cwd=work)
    concat = "\n".join(f"file 'scene-{i:02}/clip.mp4'" for i in range(len(scenes)))
    (directory / "concat.txt").write_text(concat, encoding="utf-8")
    run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-c", "copy", "-movflags", "+faststart", "video.mp4",
    ], cwd=directory)
    run([
        "ffmpeg", "-y", "-v", "error", "-i", "video.mp4", "-vn", "-c:a", "copy", "audio.m4a",
    ], cwd=directory)
    (directory / "subtitles.srt").write_text("\n".join(subtitles_all), encoding="utf-8")
    (directory / "poster.png").write_bytes((directory / "scene-00/card.png").read_bytes())
    return offset
