from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from anime_tools.config import ModelScopeVideoSettings


Transport = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]]], Tuple[int, Dict[str, str], bytes]]
Sleep = Callable[[float], None]
Log = Callable[[str], None]


@dataclass(frozen=True)
class ImageToVideoTask:
    task_id: str
    video_url: str


class DashScopeImageToVideoClient:
    def __init__(
        self,
        settings: ModelScopeVideoSettings,
        transport: Transport | None = None,
        sleep: Sleep | None = None,
        log: Log | None = None,
    ):
        self.settings = settings
        self.transport = transport or _urllib_transport
        self.sleep = sleep or time.sleep
        self.log = log or (lambda _message: None)

    def generate_video(self, image_url: str, prompt: str) -> bytes:
        task_id = self.create_task(image_url, prompt)
        self.log(f"DashScope task created: {task_id}")
        task = self.wait_for_task(task_id)
        self.log(f"DashScope task succeeded: {task_id}")
        return self.download_video(task.video_url)

    def create_task(self, image_url: str, prompt: str) -> str:
        _validate_settings(self.settings)
        payload = {
            "model": self.settings.model,
            "input": {
                "prompt": prompt,
                "img_url": image_url,
            },
            "parameters": {
                "duration": self.settings.duration,
                "resolution": self.settings.resolution,
            },
        }
        status, _response_headers, body = self.transport(
            "POST",
            f"{self.settings.base_url}/services/aigc/video-generation/video-synthesis",
            _headers(self.settings, async_task=True),
            payload,
        )
        data = _read_json_response(status, body, "创建图生视频任务失败")
        task_id = str(data.get("output", {}).get("task_id", "")).strip()
        if not task_id:
            raise RuntimeError("图生视频任务响应缺少 task_id")
        return task_id

    def wait_for_task(self, task_id: str) -> ImageToVideoTask:
        started = time.time()
        while True:
            status, _headers_value, body = self._request_with_retry(
                "GET",
                f"{self.settings.base_url}/tasks/{task_id}",
                _headers(self.settings, async_task=False),
                None,
            )
            data = _read_json_response(status, body, "查询图生视频任务失败")
            output = data.get("output", {})
            task_status = str(output.get("task_status", "")).upper()
            self.log(f"DashScope task status: {task_id} {task_status or 'UNKNOWN'}")
            if task_status == "SUCCEEDED":
                video_url = str(output.get("video_url", "")).strip()
                if not video_url:
                    raise RuntimeError("图生视频任务成功但缺少 video_url")
                return ImageToVideoTask(task_id=task_id, video_url=video_url)
            if task_status in {"FAILED", "CANCELED", "UNKNOWN"}:
                message = output.get("message") or data.get("message") or task_status
                raise RuntimeError(f"图生视频任务失败: {message}")
            if time.time() - started > self.settings.timeout_seconds:
                raise TimeoutError(f"图生视频任务超时: {task_id}")
            self.sleep(self.settings.poll_interval_seconds)

    def download_video(self, video_url: str) -> bytes:
        status, _headers_value, body = self._request_with_retry("GET", video_url, {}, None)
        if status >= 400:
            raise RuntimeError(f"下载图生视频失败: HTTP {status} {body[:200]!r}")
        return body

    def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, str], bytes]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return self.transport(method, url, headers, payload)
            except urllib.error.URLError as exc:
                last_error = exc
                self.log(f"Temporary network error, retry {attempt}/3: {exc}")
                self.sleep(min(2 * attempt, 5))
        raise RuntimeError(f"网络请求失败，已重试 3 次: {last_error}")


def _validate_settings(settings: ModelScopeVideoSettings) -> None:
    if not settings.api_key:
        raise RuntimeError("缺少 ModelScope/DashScope 图生视频配置: modelscope_video.api_key")
    if settings.duration <= 0:
        raise ValueError("modelscope_video.duration 必须大于 0")


def image_file_to_data_url(image_path: Path) -> str:
    if not image_path.is_file():
        raise FileNotFoundError(str(image_path))
    content_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{data}"


def _headers(settings: ModelScopeVideoSettings, async_task: bool) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    if async_task:
        headers["X-DashScope-Async"] = "enable"
    return headers


def _read_json_response(status: int, body: bytes, message: str) -> dict[str, Any]:
    if status >= 400:
        raise RuntimeError(f"{message}: HTTP {status} {body[:300]!r}")
    return json.loads(body.decode("utf-8"))


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
) -> tuple[int, dict[str, str], bytes]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as exc:
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, response_headers, exc.read()
