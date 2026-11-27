"""一期项目演示素材的接收与固化。

上传只接受请求体里的原始字节，**从不**按 `source` URL 下载远程文件；`source` 只作为
可追溯的 HTTPS 署名写进 manifest。素材与 manifest 都落在 `settings.daily_assets_dir`
（默认 `data/video-assets`）：`<owner>--<repo>-<uuid><后缀>` 是固化副本，
`<owner>--<repo>.json` 记录 `{"file", "source"}`，渲染阶段只认这份 manifest。

外部二进制：`ffprobe` 读取 MP4 的时长与视频流；图片用 Pillow 解码校验。

失败行为：非法项目名、非 HTTPS 或带凭据的来源、超限、空文件、无法解码都抛
`HTTPException`；落盘使用临时文件加 `replace` 原子替换，失败时清理临时文件，
不会留下半成品素材或指向不存在文件的 manifest。
"""
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

# 单次上传上限 100 MiB；超限在流式读取过程中立即拒绝，避免把整段请求体落盘。
MAX_ASSET_BYTES = 100 * 1024 * 1024


async def receive(request: Request, owner: str, repo: str, filename: str, source: str) -> dict:
    """接收一期项目的演示素材并原子落盘。

    `source` 只作为 HTTPS 署名记录进 manifest，绝不据此下载远程内容。

    Args:
        request: FastAPI 请求，请求体本身就是原始文件字节，按块流式读取。
        owner: GitHub 仓库 owner，必须匹配 `[A-Za-z0-9_.-]+`。
        repo: 仓库名，规则同 `owner`；两者共同决定 manifest 文件名。
        filename: 客户端提供的文件名，只用后缀判断类型。
        source: 公开的 HTTPS 来源，禁止携带用户名、密码。

    Returns:
        `{"project", "status": "ready", "bytes"}`；成功后渲染阶段使用固化副本。

    Raises:
        HTTPException: 422 表示名称、来源、格式或解码不合法，413 表示超过
            `MAX_ASSET_BYTES`；校验失败时不保留任何文件。
    """
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
