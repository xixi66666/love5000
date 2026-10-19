import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.daily.remotion import asset_for, prepare
from app.daily.speech import align_script, group_boundaries, mimo_speech


def test_caption_groups_keep_measured_boundaries():
    cues = group_boundaries([
        {"text": "输入", "start": 0.2, "end": 0.5},
        {"text": "文字", "start": 0.5, "end": 0.9},
        {"text": "生成视频。", "start": 1.6, "end": 2.8},
    ])
    assert cues == [{"text": "输入文字", "start": 0.2, "end": 0.9},
                    {"text": "生成视频。", "start": 1.6, "end": 2.8}]


def test_caption_alignment_preserves_script_and_corrects_asr_names():
    cues = align_script("Remotion，用代码做视频。", [
        {"text": "任魔神", "start": 0.2, "end": 0.9},
        {"text": "用代碼做視頻", "start": 1.1, "end": 2.8},
    ])
    assert "".join(cue["text"] for cue in cues) == "Remotion，用代码做视频。"
    assert cues[0]["start"] == 0.2
    assert cues[-1]["end"] == 2.8


def test_caption_alignment_rejects_unrelated_audio():
    with pytest.raises(RuntimeError, match="reliably aligned"):
        align_script("输入文字生成视频。", [{"text": "今天天气晴朗", "start": 0.1, "end": 2.0}])


def test_sample_provisions_its_own_remotion_assets(tmp_path, monkeypatch):
    from app.daily import sample

    monkeypatch.setattr(sample.store, "root", lambda: tmp_path / "reports")
    calls = []
    monkeypatch.setattr(sample, "invoke_renderer", lambda directory, **kwargs: calls.append((directory, kwargs)))

    def render(scenes, day, directory, sources):
        assert sources.parent == directory
        assert json.loads((sources / "remotion-dev--remotion.json").read_text())["file"] == "demo.mp4"
        assert calls == [(sources, {"demo": True})]
        assert scenes[1]["heading"] == "remotion-dev/remotion"
        return 27

    monkeypatch.setattr(sample, "render", render)
    assert sample.generate_sample()["status"] == "sample_ready"


def test_missing_demo_fails_before_spending_tts_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_require_demo_assets", True)
    monkeypatch.setattr(settings, "daily_assets_dir", str(tmp_path / "assets"))
    voice = AsyncMock()
    monkeypatch.setattr("app.daily.remotion.synthesize", voice)
    with pytest.raises(RuntimeError, match="demo assets required"):
        prepare([{"heading": "org/repo"}], "2026-10-19", tmp_path)
    voice.assert_not_called()


def test_local_source_assets_cannot_escape_root(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    work = tmp_path / "report" / "scene-00"
    work.mkdir(parents=True)
    (tmp_path / "private.mp4").write_bytes(b"private")
    (assets / "org--repo.json").write_text(json.dumps({
        "file": "../private.mp4", "source": "https://github.com/org/repo",
    }))
    monkeypatch.setattr(settings, "daily_assets_dir", str(assets))
    with pytest.raises(ValueError, match="inside"):
        asset_for({"heading": "org/repo"}, work)


def test_manifest_frame_rounding_matches_cumulative_subtitle_offsets(tmp_path, monkeypatch):
    def voice(text, directory):
        audio = directory / "voice.wav"
        audio.write_bytes(b"mock")
        return audio, [{"text": text, "start": 0.1, "end": 1.005}]

    monkeypatch.setattr("app.daily.remotion.synthesize", voice)
    monkeypatch.setattr("app.daily.remotion.run", lambda args: '{"format":{"duration":"1.005"}}')
    monkeypatch.setattr("app.daily.remotion.asset_for", lambda *args: None)
    face = tmp_path / "font.ttf"
    face.write_bytes(b"font")
    monkeypatch.setattr("app.daily.media.font", lambda size: type("Face", (), {"path": str(face)})())
    output = tmp_path / "report"
    output.mkdir()
    result = prepare([{"heading": "项目", "narration": "用途"}] * 2, "2026-10-19", output)
    assert result["scenes"][0]["durationInFrames"] == 31
    assert "00:00:01,133" in (output / "subtitles.srt").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_mimo_does_not_send_keys_to_non_https_remote_service(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "mimo_api_key", type(settings.mimo_api_key)("test-only"))
    monkeypatch.setattr(settings, "mimo_api_base", "http://remote.example/v1")
    with pytest.raises(ValueError, match="HTTPS"):
        await mimo_speech("测试", tmp_path / "voice.wav")


@pytest.mark.asyncio
async def test_mimo_errors_are_sanitized(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "mimo_api_key", type(settings.mimo_api_key)("test-only"))
    monkeypatch.setattr(settings, "mimo_api_base", "https://api.xiaomimimo.com/v1")
    request = httpx.Request("POST", "https://api.xiaomimimo.com/v1/chat/completions")
    post = AsyncMock(side_effect=httpx.RequestError("secret-provider-response", request=request))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(RuntimeError) as error:
        await mimo_speech("测试", tmp_path / "voice.wav")
    assert "secret-provider-response" not in str(error.value)
