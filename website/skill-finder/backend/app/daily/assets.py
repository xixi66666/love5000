"""接收本地演示素材，不根据来源 URL 下载远程文件。"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException, Request
from PIL import Image

from app.core.config import settings
from app.daily.media import run

MAX_ASSET_BYTES = 100 * 1024 * 1024


async def receive(request: Request, owner: str, repo: str, filename: str, source: str) -> dict:
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in {".", ".."}
               for part in (owner, repo)):
        raise HTTPException(422, "Invalid project name")
    url = urlsplit(source)
    if url.scheme != "https" or not url.netloc or url.username or url.password or len(source) > 500:
        raise HTTPException(422, "Provide an HTTPS source attribution without credentials")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(422, "Use an MP4, PNG or JPEG asset")
    root = Path(settings.daily_assets_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stem = owner + "--" + repo
    destination = root / (stem + "-" + uuid4().hex + suffix)
    temporary = root / (".upload-" + uuid4().hex + suffix)
    manifest_temp = root / (".asset-" + uuid4().hex + ".tmp")
    total = 0
    try:
        with temporary.open("xb") as stream:
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_ASSET_BYTES:
                    raise HTTPException(413, "Asset exceeds 100 MiB")
                stream.write(chunk)
        if not total:
            raise HTTPException(422, "Asset is empty")
        try:
            if suffix == ".mp4":
                value = json.loads(run([
                    settings.daily_ffprobe_command, "-v", "quiet", "-show_streams", "-show_format",
                    "-of", "json", str(temporary),
                ], timeout=30))
                duration = float(value["format"]["duration"])
                if not math.isfinite(duration) or not 0 < duration <= 600 or not any(
                    item.get("codec_type") == "video" for item in value["streams"]
                ):
                    raise ValueError("Invalid video")
            else:
                with Image.open(temporary) as image:
                    if image.width * image.height > 40_000_000 or image.format not in {"PNG", "JPEG"}:
                        raise ValueError("Invalid image")
                    image.verify()
        except (OSError, ValueError, KeyError, RuntimeError, Image.DecompressionBombError):
            raise HTTPException(422, "Asset could not be decoded; check the file and media tools") from None
        temporary.replace(destination)
        manifest_temp.write_text(json.dumps({"file": destination.name, "source": source}, ensure_ascii=False),
                                 encoding="utf-8")
        manifest_temp.replace(root / (stem + ".json"))
    finally:
        temporary.unlink(missing_ok=True)
        manifest_temp.unlink(missing_ok=True)
    return {"project": owner + "/" + repo, "status": "ready", "bytes": total}
