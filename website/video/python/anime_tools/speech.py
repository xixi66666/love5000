from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict

from anime_tools.config import AppSettings, TencentCloudTtsSettings
from anime_tools.openai_client import OpenAICompatibleClient


TencentSynthesizer = Callable[[TencentCloudTtsSettings, str, str], Dict[str, Any]]
SessionIdProvider = Callable[[], str]


class TencentCloudTtsClient:
    def __init__(
        self,
        settings: TencentCloudTtsSettings,
        synthesizer: TencentSynthesizer | None = None,
        session_id_provider: SessionIdProvider | None = None,
    ):
        self.settings = settings
        self.synthesizer = synthesizer or _synthesize_with_tencent_sdk
        self.session_id_provider = session_id_provider or _default_session_id

    def generate_speech(self, text: str) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("旁白文本不能为空")
        _validate_tencent_settings(self.settings)

        response = self.synthesizer(self.settings, clean_text, self.session_id_provider())
        audio = response.get("Audio")
        if not audio:
            raise RuntimeError("腾讯云 TTS 返回中没有 Audio 字段")
        return base64.b64decode(audio)


def create_speech_client(
    settings: AppSettings,
    openai_client: OpenAICompatibleClient | None = None,
) -> Any:
    provider = settings.tts.provider
    if provider == "openai":
        return openai_client or OpenAICompatibleClient(settings.openai)
    if provider == "tencent":
        return TencentCloudTtsClient(settings.tencent_tts)
    raise ValueError(f"不支持的 TTS Provider: {settings.tts.provider}")


def _validate_tencent_settings(settings: TencentCloudTtsSettings) -> None:
    if not settings.secret_id:
        raise RuntimeError("缺少腾讯云 TTS 配置: tencent_tts.secret_id")
    if not settings.secret_key:
        raise RuntimeError("缺少腾讯云 TTS 配置: tencent_tts.secret_key")
    if settings.codec not in {"mp3", "wav", "pcm"}:
        raise ValueError("腾讯云 TTS codec 只支持 mp3、wav、pcm")
    if settings.sample_rate not in {8000, 16000}:
        raise ValueError("腾讯云 TTS sample_rate 只支持 8000 或 16000")
    if settings.primary_language not in {1, 2}:
        raise ValueError("腾讯云 TTS primary_language 只支持 1 中文或 2 英文")


def _synthesize_with_tencent_sdk(settings: TencentCloudTtsSettings, text: str, session_id: str) -> dict[str, Any]:
    _ensure_vendor_on_path()
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.tts.v20190823 import models, tts_client
    except ImportError as exc:
        raise RuntimeError("缺少腾讯云 TTS SDK，请先安装 tencentcloud-sdk-python-tts") from exc

    cred = credential.Credential(settings.secret_id, settings.secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = "tts.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = tts_client.TtsClient(cred, settings.region, client_profile)

    request = models.TextToVoiceRequest()
    request.Text = text
    request.SessionId = session_id
    request.ModelType = 1
    request.VoiceType = settings.voice_type
    request.PrimaryLanguage = settings.primary_language
    request.Codec = settings.codec
    request.SampleRate = settings.sample_rate
    request.Speed = settings.speed
    request.Volume = settings.volume

    response = client.TextToVoice(request)
    return json.loads(response.to_json_string())


def _ensure_vendor_on_path() -> None:
    vendor = Path(__file__).resolve().parent.parent / ".vendor"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))


def _default_session_id() -> str:
    return f"video-{int(time.time() * 1000)}"
