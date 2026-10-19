"""中文配音与真实字幕时间轴；供应商失败时不生成静音占位。"""
from __future__ import annotations

import asyncio
import base64
import binascii
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.daily.progress import current


def group_boundaries(boundaries: list[dict]) -> list[dict]:
    """按真实词边界组成便于手机阅读的意群，保留原时间。"""
    result: list[dict] = []
    text, start, end = "", 0.0, 0.0
    for item in boundaries:
        piece = item["text"].strip()
        if not piece or item["end"] <= item["start"]:
            continue
        if text and (len(text) + len(piece) > 18 or item["start"] - end > 0.45):
            result.append({"text": text, "start": start, "end": end})
            text = ""
        if not text:
            start = item["start"]
        if text and text[-1].isascii() and piece[0].isascii():
            text += " "
        text += piece
        end = item["end"]
        if piece[-1] in "。！？!?；;":
            result.append({"text": text, "start": start, "end": end})
            text = ""
    if text:
        result.append({"text": text, "start": start, "end": end})
    if not result:
        raise RuntimeError("No trustworthy speech timestamps returned")
    return result


def align_script(text: str, boundaries: list[dict]) -> list[dict]:
    """以 ASR 真实边界对齐已确认原稿，修正专有名词和繁简识别错误。

    不生成逐字高亮时间；无法可靠匹配时失败，不回退到按字数均分。
    """
    def normalized(value):
        return "".join(char.lower() for char in value if char.isalnum())

    original = normalized(text)
    recognized, times = "", []
    for word in boundaries:
        letters = normalized(word["text"])
        recognized += letters
        times.extend([(word["start"], word["end"])] * len(letters))
    matcher = SequenceMatcher(None, original, recognized, autojunk=False)
    chinese = sum(not char.isascii() for char in original)
    anchored_chinese = sum(
        sum(not char.isascii() for char in original[block.a:block.a + block.size])
        for block in matcher.get_matching_blocks()
    )
    # 英文名占比高时全串相似度会偏低，允许足够的中文上下文作为锚点。
    supported_by_context = anchored_chinese >= 3 and anchored_chinese / max(1, chinese) >= 0.5
    if not original or not recognized or (matcher.ratio() < 0.35 and not supported_by_context):
        raise RuntimeError("Narration could not be reliably aligned; review the audio")
    pieces = re.findall(r"[^，。！？；,.!?;]+[，。！？；,.!?;]?", text)
    result, cursor = [], 0
    for piece in pieces:
        length = len(normalized(piece))
        left, right = cursor, cursor + length
        cursor = right
        spans = []
        for operation, a0, a1, b0, b1 in matcher.get_opcodes():
            if a1 <= left or a0 >= right or b1 <= b0:
                continue
            if operation == "equal":
                spans.append((b0 + max(left, a0) - a0, b0 + min(right, a1) - a0))
            elif operation == "replace":
                spans.append((b0, b1))
        if not spans:
            raise RuntimeError("A narration phrase has no measured timestamp; review the audio")
        start = min(times[b0][0] for b0, _ in spans)
        end = max(times[b1 - 1][1] for _, b1 in spans)
        if result and start < result[-1]["end"] - 0.01:
            result[-1]["text"] += piece.strip()
            result[-1]["end"] = max(result[-1]["end"], end)
        else:
            result.append({"text": piece.strip(), "start": start, "end": end})
    return result


async def edge_speech(text: str, target: Path) -> list[dict]:
    import edge_tts

    communicator = edge_tts.Communicate(text, settings.daily_tts_voice, rate="+8%", boundary="WordBoundary")
    boundaries = []
    with target.open("wb") as stream:
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                stream.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append({
                    "text": chunk["text"], "start": chunk["offset"] / 10_000_000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                })
    if target.stat().st_size < 1000:
        raise RuntimeError("TTS returned empty audio")
    return group_boundaries(boundaries)


async def mimo_speech(text: str, target: Path) -> None:
    key = settings.mimo_api_key.get_secret_value()
    if not key:
        raise RuntimeError("MiMo TTS requires MIMO_API_KEY in backend/.env or environment")
    base = settings.mimo_api_base.rstrip("/")
    url = urlsplit(base)
    if url.username or url.password or url.query or url.fragment or (
        url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"})
    ):
        raise ValueError("MIMO_API_BASE must use HTTPS or local HTTP without credentials")
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(base + "/chat/completions", headers={"api-key": key}, json={
                "model": settings.mimo_tts_model, "stream": False,
                "messages": [
                    {"role": "user", "content": settings.mimo_tts_style},
                    {"role": "assistant", "content": text},
                ],
                "audio": {"format": "wav", "voice": settings.mimo_tts_voice},
            })
            response.raise_for_status()
            audio = base64.b64decode(response.json()["choices"][0]["message"]["audio"]["data"], validate=True)
            if len(audio) < 1000 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
                raise ValueError("Invalid WAV audio")
    except (httpx.HTTPError, KeyError, IndexError, ValueError, binascii.Error):
        raise RuntimeError("MiMo TTS failed; check private provider configuration and quota") from None
    target.write_bytes(audio)


@lru_cache(maxsize=1)
def whisper_model(name: str):
    # MiMo TTS 当前官方接口未承诺词时间戳，不能伪造；对实际音轨做转写取时序。
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("MiMo captions require: uv sync --extra captions") from None
    return WhisperModel(name, device="cpu", compute_type="int8")


def transcribe(audio: Path, text: str | None = None) -> list[dict]:
    model = whisper_model(settings.daily_whisper_model)
    segments, _ = model.transcribe(str(audio), language="zh", word_timestamps=True, vad_filter=True,
                                  initial_prompt=text or "Remotion, React, JSON, GitHub, AI, Skill Finder, MCP")
    boundaries = [
        {"text": word.word, "start": word.start, "end": word.end}
        for segment in segments for word in (segment.words or [])
    ]
    return align_script(text, boundaries) if text else group_boundaries(boundaries)


def synthesize(text: str, directory: Path) -> tuple[Path, list[dict]]:
    progress = current()
    if progress:
        progress.begin("voice", "正在合成当前段落的人声。")
    if settings.daily_tts_provider == "mimo":
        audio = directory / "voice.wav"
        asyncio.run(mimo_speech(text, audio))
        if progress:
            progress.tick("voice", "当前段落的 MiMo 配音已生成。")
            progress.begin("captions", "正在对齐当前段落的实际音轨，首次使用可能需要下载模型。")
        captions = transcribe(audio, text)
    else:
        audio = directory / "voice.mp3"
        captions = asyncio.run(edge_speech(text, audio))
        if progress:
            progress.tick("voice", "当前段落的 Edge 配音已生成。")
            progress.begin("captions", "正在整理供应商返回的真实时间戳。")
    if progress:
        progress.tick("captions", "当前段落的字幕已对齐。")
    return audio, captions
