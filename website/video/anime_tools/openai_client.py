from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Tuple

from anime_tools.config import OpenAISettings


Transport = Callable[[str, str, Dict[str, str], Dict[str, Any]], Tuple[int, Dict[str, str], bytes]]


class OpenAICompatibleClient:
    def __init__(self, settings: OpenAISettings, transport: Transport | None = None):
        self.settings = settings
        self.transport = transport or _urllib_transport

    def generate_story_package(self, theme: str) -> dict[str, Any]:
        payload = {
            "model": self.settings.text_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是原创国风动漫短片编剧和分镜师。"
                        "只输出 JSON，不要 Markdown。"
                    ),
                },
                {
                    "role": "user",
                    "content": _story_prompt(theme),
                },
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }
        data = self._post_json("/chat/completions", payload)
        content = data["choices"][0]["message"]["content"]
        package = json.loads(content)
        _validate_story_package(package)
        return package

    def generate_image(self, prompt: str) -> bytes:
        payload = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "size": "1024x1792",
            "quality": "low",
            "output_format": "png",
        }
        data = self._post_json("/images/generations", payload)
        item = data["data"][0]
        if "b64_json" in item:
            return base64.b64decode(item["b64_json"])
        if "url" in item:
            return _download_bytes(item["url"])
        raise RuntimeError("图片接口返回中没有 b64_json 或 url")

    def generate_speech(self, text: str) -> bytes:
        payload = {
            "model": self.settings.tts_model,
            "voice": self.settings.tts_voice,
            "input": text,
            "format": "mp3",
        }
        status, headers, body = self._request("/audio/speech", payload)
        content_type = headers.get("content-type", "")
        if status >= 400:
            raise RuntimeError(f"TTS 请求失败: HTTP {status} {body[:200]!r}")
        if "application/json" in content_type:
            data = json.loads(body.decode("utf-8"))
            if "audio" in data:
                return base64.b64decode(data["audio"])
            raise RuntimeError("TTS JSON 返回中没有 audio 字段")
        return body

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        status, _headers, body = self._request(path, payload)
        if status >= 400:
            raise RuntimeError(f"接口请求失败: HTTP {status} {body[:300]!r}")
        return json.loads(body.decode("utf-8"))

    def _request(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        return self.transport("POST", f"{self.settings.base_url}{path}", headers, payload)


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as exc:
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, response_headers, exc.read()


def _download_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()


def _story_prompt(theme: str) -> str:
    return f"""
请根据下面主题，生成一条 15 秒、9:16 竖屏、国风玄幻动漫动态分镜短片方案。

主题：{theme}

要求：
1. 标题必须短，适合作为文件夹名，不超过 8 个中文字符。
2. 总共 4 个镜头，时长分别接近 3.5、3.5、4、4 秒。
3. 每个镜头都要有 subtitle 和 image_prompt。
4. image_prompt 要适合 AI 生成动漫关键帧，强调国风玄幻、电影感、竖屏构图、角色一致性。
5. narration 是完整旁白，适合 TTS 朗读，总字数 60 字以内。

JSON 格式：
{{
  "title": "短标题",
  "narration": "完整旁白",
  "shots": [
    {{
      "id": "shot_01",
      "duration": 3.5,
      "description": "画面描述",
      "subtitle": "字幕",
      "image_prompt": "图片提示词"
    }}
  ]
}}
""".strip()


def _validate_story_package(package: dict[str, Any]) -> None:
    if not package.get("title"):
        raise ValueError("文本模型返回缺少 title")
    if not package.get("narration"):
        raise ValueError("文本模型返回缺少 narration")
    shots = package.get("shots")
    if not isinstance(shots, list) or len(shots) != 4:
        raise ValueError("文本模型必须返回 4 个镜头")
    for index, shot in enumerate(shots, start=1):
        for field in ["id", "duration", "description", "subtitle", "image_prompt"]:
            if field not in shot:
                raise ValueError(f"第 {index} 个镜头缺少字段: {field}")
