from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Tuple


Transport = Callable[[str, str, Dict[str, str], Dict[str, Any], float], Tuple[int, Dict[str, str], bytes]]


class LocalWanImageToVideoProvider:
    """本地 Wan/Wan2.2 图生视频 HTTP 服务适配器。

    默认约定：
    - POST {base_url}{endpoint}
    - JSON 入参包含 shot_id、prompt、duration、resolution、image(data URL)
    - 响应可以是 video_base64、video_url，或直接返回 video/* 二进制。
    """

    def __init__(
        self,
        base_url: str,
        endpoint: str = "/generate",
        timeout_seconds: float = 600,
        transport: Transport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _urllib_transport

    def generate(self, request: Any) -> bytes:
        if not self.base_url:
            raise RuntimeError("缺少本地 Wan 图生视频服务地址: local_wan_video.base_url")

        payload = {
            "shot_id": request.shot_id,
            "prompt": request.prompt,
            "duration": request.duration,
            "resolution": request.resolution,
            "image": _image_file_to_data_url(request.image_path),
        }
        status, headers, body = self.transport(
            "POST",
            f"{self.base_url}{self.endpoint}",
            {"Content-Type": "application/json"},
            payload,
            self.timeout_seconds,
        )
        if status >= 400:
            raise RuntimeError(f"本地 Wan 图生视频请求失败: HTTP {status} {body[:300]!r}")

        content_type = headers.get("content-type", "")
        if content_type.startswith("video/") or content_type == "application/octet-stream":
            return body

        data = json.loads(body.decode("utf-8"))
        if data.get("success") is False:
            raise RuntimeError(str(data.get("message") or "本地 Wan 图生视频生成失败"))
        if data.get("video_base64"):
            return base64.b64decode(str(data["video_base64"]))
        if data.get("video_url"):
            return _download_bytes(str(data["video_url"]), self.timeout_seconds)
        raise RuntimeError("本地 Wan 响应中缺少 video_base64 或 video_url")


def _image_file_to_data_url(image_path: Path) -> str:
    if not image_path.is_file():
        raise FileNotFoundError(str(image_path))
    content_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{data}"


def _download_bytes(url: str, timeout_seconds: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        return response.read()


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as exc:
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, response_headers, exc.read()
