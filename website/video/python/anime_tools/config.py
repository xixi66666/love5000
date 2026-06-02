from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = WORKSPACE_ROOT / "python"
CONFIG_DIR = WORKSPACE_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.local.json"
LEGACY_CONFIG_PATH = WORKSPACE_ROOT / "config.local.json"
EXAMPLE_CONFIG_PATH = CONFIG_DIR / "config.example.json"
SENSITIVE_CONFIG_FIELDS = {
    ("openai", "api_key"),
    ("tencent_tts", "secret_id"),
    ("tencent_tts", "secret_key"),
    ("modelscope_video", "api_key"),
}


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
class TtsSettings:
    provider: str = "openai"

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", self.provider.strip().lower() or "openai")


@dataclass(frozen=True)
class TencentCloudTtsSettings:
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    voice_type: int = 101001
    primary_language: int = 1
    codec: str = "mp3"
    sample_rate: int = 16000
    speed: int = 0
    volume: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "secret_id", self.secret_id.strip())
        object.__setattr__(self, "secret_key", self.secret_key.strip())
        object.__setattr__(self, "region", self.region.strip() or "ap-guangzhou")
        object.__setattr__(self, "codec", self.codec.strip().lower() or "mp3")

    @classmethod
    def from_env(cls) -> "TencentCloudTtsSettings":
        return cls(
            secret_id=os.environ.get("TENCENTCLOUD_SECRET_ID", ""),
            secret_key=os.environ.get("TENCENTCLOUD_SECRET_KEY", ""),
            region=os.environ.get("TENCENTCLOUD_TTS_REGION", "ap-guangzhou"),
            voice_type=int(os.environ.get("TENCENTCLOUD_TTS_VOICE_TYPE", "101001")),
            primary_language=int(os.environ.get("TENCENTCLOUD_TTS_PRIMARY_LANGUAGE", "1")),
            codec=os.environ.get("TENCENTCLOUD_TTS_CODEC", "mp3"),
            sample_rate=int(os.environ.get("TENCENTCLOUD_TTS_SAMPLE_RATE", "16000")),
            speed=int(os.environ.get("TENCENTCLOUD_TTS_SPEED", "0")),
            volume=int(os.environ.get("TENCENTCLOUD_TTS_VOLUME", "5")),
        )


@dataclass(frozen=True)
class ModelScopeVideoSettings:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    model: str = "wanx2.1-i2v-plus"
    duration: int = 5
    resolution: str = "720P"
    poll_interval_seconds: float = 5.0
    timeout_seconds: float = 600.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_key", self.api_key.strip())
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
        object.__setattr__(self, "model", self.model.strip() or "wanx2.1-i2v-plus")
        object.__setattr__(self, "resolution", self.resolution.strip() or "720P")


@dataclass(frozen=True)
class AppSettings:
    openai: OpenAISettings
    default_bgm: Path
    tts: TtsSettings = TtsSettings()
    tencent_tts: TencentCloudTtsSettings = TencentCloudTtsSettings()
    modelscope_video: ModelScopeVideoSettings = ModelScopeVideoSettings()

    @classmethod
    def from_json(cls, config_path: Path) -> "AppSettings":
        config_path = resolve_config_path(config_path)
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
            default_bgm = WORKSPACE_ROOT / default_bgm
        tts_data = data.get("tts", {})
        tencent_data = data.get("tencent_tts", {})
        modelscope_video_data = data.get("modelscope_video", {})

        return cls(
            openai=OpenAISettings(
                api_key=api_key,
                base_url=openai_data.get("base_url", "https://api.openai.com/v1"),
                text_model=openai_data.get("text_model", "gpt-4.1-mini"),
                image_model=openai_data.get("image_model", "gpt-image-1"),
                tts_model=openai_data.get("tts_model", "gpt-4o-mini-tts"),
                tts_voice=openai_data.get("tts_voice", "alloy"),
            ),
            tts=TtsSettings(provider=tts_data.get("provider", "openai")),
            tencent_tts=TencentCloudTtsSettings(
                secret_id=tencent_data.get("secret_id", ""),
                secret_key=tencent_data.get("secret_key", ""),
                region=tencent_data.get("region", "ap-guangzhou"),
                voice_type=int(tencent_data.get("voice_type", 101001)),
                primary_language=int(tencent_data.get("primary_language", 1)),
                codec=tencent_data.get("codec", "mp3"),
                sample_rate=int(tencent_data.get("sample_rate", 16000)),
                speed=int(tencent_data.get("speed", 0)),
                volume=int(tencent_data.get("volume", 5)),
            ),
            modelscope_video=ModelScopeVideoSettings(
                api_key=modelscope_video_data.get("api_key", ""),
                base_url=modelscope_video_data.get("base_url", "https://dashscope.aliyuncs.com/api/v1"),
                model=modelscope_video_data.get("model", "wanx2.1-i2v-plus"),
                duration=int(modelscope_video_data.get("duration", 5)),
                resolution=modelscope_video_data.get("resolution", "720P"),
                poll_interval_seconds=float(modelscope_video_data.get("poll_interval_seconds", 5.0)),
                timeout_seconds=float(modelscope_video_data.get("timeout_seconds", 600.0)),
            ),
            default_bgm=default_bgm,
        )


def resolve_config_path(config_path: str | Path | None = None) -> Path:
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = WORKSPACE_ROOT / path
        return path
    if DEFAULT_CONFIG_PATH.is_file():
        return DEFAULT_CONFIG_PATH
    return LEGACY_CONFIG_PATH


def load_editable_config() -> dict:
    path = resolve_config_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    elif EXAMPLE_CONFIG_PATH.is_file():
        data = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        data = _default_config()
    return {
        "success": True,
        "config_path": _display_config_path(DEFAULT_CONFIG_PATH),
        "config": mask_sensitive_config(data),
    }


def save_editable_config(update: dict) -> dict:
    if not isinstance(update, dict):
        raise ValueError("配置内容必须是 JSON 对象")

    current_path = resolve_config_path()
    if current_path.is_file():
        current = json.loads(current_path.read_text(encoding="utf-8"))
    elif EXAMPLE_CONFIG_PATH.is_file():
        current = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        current = _default_config()

    incoming = update.get("config", update)
    if not isinstance(incoming, dict):
        raise ValueError("config 必须是 JSON 对象")

    merged = _merge_config(current, incoming)
    _validate_editable_config(merged)
    _atomic_write_json(DEFAULT_CONFIG_PATH, merged)
    return {
        "success": True,
        "config_path": _display_config_path(DEFAULT_CONFIG_PATH),
        "config": mask_sensitive_config(merged),
    }


def mask_sensitive_config(data: dict) -> dict:
    masked = json.loads(json.dumps(data, ensure_ascii=False))
    for section, field in SENSITIVE_CONFIG_FIELDS:
        if isinstance(masked.get(section), dict):
            masked[section][field] = ""
    return masked


def _merge_config(current: dict, incoming: dict) -> dict:
    merged = json.loads(json.dumps(current, ensure_ascii=False))
    for section, value in incoming.items():
        if isinstance(value, dict):
            target = merged.setdefault(section, {})
            if not isinstance(target, dict):
                target = {}
                merged[section] = target
            for field, field_value in value.items():
                if (section, field) in SENSITIVE_CONFIG_FIELDS and str(field_value).strip() == "":
                    continue
                target[field] = field_value
        else:
            merged[section] = value
    return merged


def _validate_editable_config(data: dict) -> None:
    tts = data.setdefault("tts", {})
    provider = str(tts.get("provider", "openai")).strip().lower() or "openai"
    if provider not in {"openai", "tencent"}:
        raise ValueError("tts.provider 只能是 openai 或 tencent")
    tts["provider"] = provider

    tencent = data.setdefault("tencent_tts", {})
    for field in ["voice_type", "primary_language", "sample_rate", "speed", "volume"]:
        if field in tencent:
            tencent[field] = int(tencent[field])
    if "volume" in tencent and not 0 <= int(tencent["volume"]) <= 10:
        raise ValueError("tencent_tts.volume 必须在 0 到 10 之间")
    if "speed" in tencent and not -2 <= int(tencent["speed"]) <= 6:
        raise ValueError("tencent_tts.speed 必须在 -2 到 6 之间")

    modelscope = data.setdefault("modelscope_video", {})
    if "duration" in modelscope:
        modelscope["duration"] = int(modelscope["duration"])
    for field in ["poll_interval_seconds", "timeout_seconds"]:
        if field in modelscope:
            modelscope[field] = float(modelscope[field])
    if "duration" in modelscope and int(modelscope["duration"]) <= 0:
        raise ValueError("modelscope_video.duration 必须大于 0")
    if "timeout_seconds" in modelscope and float(modelscope["timeout_seconds"]) <= 0:
        raise ValueError("modelscope_video.timeout_seconds 必须大于 0")


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _display_config_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def _default_config() -> dict:
    return {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "text_model": "gpt-4.1-mini",
            "image_model": "gpt-image-1",
            "tts_model": "gpt-4o-mini-tts",
            "tts_voice": "alloy",
        },
        "tts": {"provider": "openai"},
        "tencent_tts": {
            "secret_id": "",
            "secret_key": "",
            "region": "ap-guangzhou",
            "voice_type": 101001,
            "primary_language": 1,
            "codec": "mp3",
            "sample_rate": 16000,
            "speed": 0,
            "volume": 5,
        },
        "modelscope_video": {
            "api_key": "",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "model": "wanx2.1-i2v-plus",
            "duration": 5,
            "resolution": "720P",
            "poll_interval_seconds": 5,
            "timeout_seconds": 600,
        },
        "assets": {"default_bgm": "assets/default_bgm.mp3"},
    }


def _normalize_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"
