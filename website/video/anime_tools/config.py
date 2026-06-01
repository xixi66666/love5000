from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    text_model: str = "gpt-4.1-mini"
    image_model: str = "gpt-image-1"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _normalize_base_url(self.base_url))

    @classmethod
    def from_env(cls) -> "OpenAISettings":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("缺少环境变量 OPENAI_API_KEY")

        return cls(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            text_model=os.environ.get("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
            image_model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            tts_model=os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.environ.get("OPENAI_TTS_VOICE", "alloy"),
        )


@dataclass(frozen=True)
class AppSettings:
    openai: OpenAISettings
    default_bgm: Path

    @classmethod
    def from_json(cls, config_path: Path) -> "AppSettings":
        if not config_path.is_file():
            raise FileNotFoundError(f"缺少配置文件: {config_path}")

        data = json.loads(config_path.read_text(encoding="utf-8"))
        openai_data = data.get("openai", {})
        api_key = str(openai_data.get("api_key", "")).strip()
        if not api_key or api_key == "请填写你的API_KEY":
            raise RuntimeError(f"请在配置文件中填写 openai.api_key: {config_path}")

        assets = data.get("assets", {})
        default_bgm = Path(assets.get("default_bgm", "assets/default_bgm.mp3"))
        if not default_bgm.is_absolute():
            default_bgm = config_path.parent / default_bgm

        return cls(
            openai=OpenAISettings(
                api_key=api_key,
                base_url=openai_data.get("base_url", "https://api.openai.com/v1"),
                text_model=openai_data.get("text_model", "gpt-4.1-mini"),
                image_model=openai_data.get("image_model", "gpt-image-1"),
                tts_model=openai_data.get("tts_model", "gpt-4o-mini-tts"),
                tts_voice=openai_data.get("tts_voice", "alloy"),
            ),
            default_bgm=default_bgm,
        )


def _normalize_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"
