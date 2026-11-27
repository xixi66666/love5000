"""旧版文字卡片视频与全局受限子进程调用。

`render` 按 `DAILY_VIDEO_RENDERER` 分派：`legacy` 使用本模块的 Pillow 卡片、Edge
TTS 与 FFmpeg 拼接（仅显式回退时使用），`hyperframes` / `remotion` 转交各自的
适配层，只有 legacy 分支会走到 `card`、`speech`、`subtitles`。

外部二进制：`ffprobe` 读取配音时长，`ffmpeg` 逐段合成并 concat 拼接；配音还会访问
Edge TTS 网络服务。`run` 是全模块统一的子进程入口：超时会连同整个进程树一起终止
（Windows 用 `taskkill /T`，POSIX 用 `killpg`），错误信息只保留程序名与退出码，
不回显环境变量、私有路径或上游 URL。

产物写入任务目录：逐段 `scene-NN/`、`video.mp4`、`audio.m4a`、`poster.png`、
`subtitles.srt`。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.daily.progress import current

WIDTH, HEIGHT = 720, 1280
BG, INK, MUTED, GREEN = "#07090c", "#f4f6f8", "#b3bbc8", "#c9fe6e"


def font(size: int):
    """按候选顺序加载中文字体。

    候选为 `DAILY_FONT`、Linux 的 Noto Sans CJK 与 Windows 的微软雅黑；返回的
    `ImageFont` 保留真实文件路径，渲染器还会复制这份字体。

    Raises:
        RuntimeError: 三个候选都不存在，避免渲染出没有字形的乱码。
    """
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
    """按像素宽度做中文友好的折行。

    逐字累加并用 `textlength` 实测宽度，超宽断行，遇到显式换行符强制断行；不按
    字数估算，因此中英文混排也不会溢出画布。
    """
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
    """生成一帧 legacy 文字卡片。

    画布固定 720×1280：栏目名、日期、大号 label、最多 3 行标题、可选 Star 增量、
    最多 5 行摘要与来源脚注；超出行数直接截断，不缩字号。
    """
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


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 900,
        env: dict[str, str] | None = None) -> str:
    """执行外部命令并返回合并后的文本输出。

    Args:
        args: 完整命令行，`args[0]` 只用于错误信息里的程序名。
        cwd: 子进程工作目录。
        timeout: 超时秒数；超时会终止整个进程树。
        env: 替换用的环境变量；`None` 表示继承当前环境。

    Returns:
        stdout 解码后的文本，非法字节替换而不抛异常。

    Raises:
        RuntimeError: 超时或非零退出；消息只保留程序名与退出码，不回显环境变量、
            私有路径或上游 URL。
    """
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, start_new_session=os.name != "nt")
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # 只终止本次创建的进程树，防止 Node 超时后遗留 Chromium / FFmpeg。
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False, timeout=30)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise RuntimeError(f"{Path(args[0]).name} timed out") from None
    if process.returncode:
        # 不回显子进程环境与上游 URL，避免细节进入公开报告。
        raise RuntimeError(f"{Path(args[0]).name} failed (exit {process.returncode})")
    return output.decode("utf-8", "replace")


async def speech(text: str, target: Path) -> None:
    """用 Edge TTS 合成一段中文配音，最多重试三次。

    每次超时 90 秒，输出小于 1 KB 视为空音频并重试；三次都失败才抛错，绝不留下
    静音占位。重试间隔按 2、4、6 秒递增。
    """
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
    """把秒数格式化为 SRT 时间戳 `HH:MM:SS,mmm`。"""
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def subtitles(text: str, duration: float, offset: float = 0, index: int = 1) -> tuple[str, int]:
    """按标点切句并把字幕时间按字数比例分配到给定总时长。

    这是 legacy 的估算路径：先把句子按 23 字硬切，再按字符数占比推进时间轴。
    正式成片必须使用 `speech.align_script` 的实测时间，不能用本函数替代。

    Returns:
        `(拼接后的 SRT 文本, 下一个可用序号)`。
    """
    chunks = [piece for piece in re.split(r"(?<=[，。！？；])", text) if piece.strip()]
    chunks = [chunk[i:i + 23] for chunk in chunks for i in range(0, len(chunk), 23)]
    total = sum(map(len, chunks)) or 1
    current, result = offset, []
    for chunk in chunks:
        end = current + duration * len(chunk) / total
        result.append(f"{index}\n{timestamp(current)} --> {timestamp(end)}\n{chunk}\n")
        current, index = end, index + 1
    return "\n".join(result), index


def render_legacy(scenes: list[dict], day: str, directory: Path) -> float:
    """legacy 引擎：Pillow 卡片加 Edge TTS，再用 FFmpeg 逐段合成并拼接。

    每个分镜写 `scene-NN/`（卡片、配音、字幕、`clip.mp4`），最后 concat 成
    `video.mp4` 并导出 `audio.m4a`、`poster.png`、`subtitles.srt`。产物固定
    720×1280 / 15 FPS，只是显式回退路径，不作为正式成片规格。

    Returns:
        成片总时长，单位秒，等于各段配音时长之和。

    Raises:
        RuntimeError: 字体或 TTS 不可用、ffprobe/ffmpeg 失败。
    """
    progress = current()
    if progress:
        progress.set("assets", "skipped", "显式 legacy 模式使用原文字卡片。")
        progress.begin("voice", "旧版 Edge 配音与卡片合成中。", total=len(scenes))
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
    if progress:
        progress.finish("voice", "旧版配音已生成。")
        progress.set("captions", "completed", "旧版字幕使用估算时间，不属于新版实测对齐。")
        progress.finish("render", "旧版卡片视频已合成。")
    return offset


def render(scenes: list[dict], day: str, directory: Path) -> float:
    """按 `DAILY_VIDEO_RENDERER` 分派渲染实现。

    legacy 在本模块内完成；hyperframes（默认）与 remotion 延迟导入，未选中的引擎
    不会触发 Node 依赖检查。三个分支都不做引擎之间的自动回退。

    Returns:
        成片时长，单位秒。
    """
    if settings.daily_video_renderer == "legacy":
        return render_legacy(scenes, day, directory)
    if settings.daily_video_renderer == "hyperframes":
        from app.daily.hyperframes import render as render_hyperframes

        return render_hyperframes(scenes, day, directory)
    from app.daily.remotion import render as render_remotion

    return render_remotion(scenes, day, directory)
