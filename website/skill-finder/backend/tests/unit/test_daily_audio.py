import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import settings
from app.daily import audio, remotion


def loudness(**changes):
    return {"input_i": "-22.1", "input_tp": "-9.2", "input_lra": "4.2",
            "input_thresh": "-32.1", "target_offset": "0.02", "output_i": "-16.0",
            "output_tp": "-3.1", "normalization_type": "linear", **changes}


def media_data(**video_changes):
    return {"format": {"duration": "4.0"}, "streams": [
        {"codec_type": "video", "width": 1080, "height": 1920, "avg_frame_rate": "30/1",
         "duration": "4.0", "start_time": "0", "codec_name": "h264", "pix_fmt": "yuv420p", **video_changes},
        {"codec_type": "audio", "sample_rate": "48000", "channels": 2,
         "codec_name": "aac", "duration": "4.0", "start_time": "0"},
    ]}


@pytest.fixture(autouse=True)
def no_background_music(monkeypatch):
    monkeypatch.setattr(settings, "daily_bgm_file", "")
    monkeypatch.setattr(settings, "daily_bgm_source", "")


def test_loudnorm_second_pass_uses_actual_measurements_and_48khz(tmp_path):
    calls = []

    def execute(args):
        calls.append(args)
        return "private diagnostic path\n" + json.dumps(loudness())

    result = audio.normalize_voice(tmp_path / "voice.wav", tmp_path / "normalized.wav", runner=execute)
    assert len(calls) == 2
    assert calls[0][-3:] == ["-f", "null", "-"]
    filters = calls[1][calls[1].index("-af") + 1]
    assert "measured_I=-22.1" in filters
    assert "measured_TP=-9.2" in filters
    assert "measured_LRA=4.2" in filters
    assert "measured_thresh=-32.1" in filters
    assert "offset=0.02:linear=true" in filters
    assert calls[1][calls[1].index("-ar") + 1] == "48000"
    assert result["output_lufs"] == -16
    assert "private" not in json.dumps(result)


def test_silent_audio_cannot_fake_successful_normalization(tmp_path):
    calls = []

    def execute(args):
        calls.append(args)
        return json.dumps(loudness(input_i="-inf"))

    with pytest.raises(RuntimeError, match="measurement"):
        audio.normalize_voice(tmp_path / "silent.wav", tmp_path / "normalized.wav", runner=execute)
    assert len(calls) == 1


def test_dynamic_mode_is_recorded_when_peak_constraints_need_compression(tmp_path):
    result = audio.normalize_voice(tmp_path / "voice.wav", tmp_path / "normalized.wav",
                                   runner=lambda args: json.dumps(loudness(normalization_type="dynamic")))
    assert result["normalization"] == "dynamic"


def test_dynamic_loudness_deviation_is_corrected_from_original_source(tmp_path):
    calls = []

    def execute(args):
        calls.append(args)
        output_i = "-16.7" if len(calls) == 2 else "-16.3"
        return json.dumps(loudness(normalization_type="dynamic", output_i=output_i))

    source = tmp_path / "voice.wav"
    result = audio.normalize_voice(source, tmp_path / "normalized.wav", runner=execute)
    assert len(calls) == 3
    assert calls[1][calls[1].index("-i") + 1] == str(source)
    assert calls[2][calls[2].index("-i") + 1] == str(source)
    assert "offset=0.72:linear=true" in calls[2][calls[2].index("-af") + 1]
    assert result["processing_passes"] == 2


@pytest.mark.parametrize("source", ["", "http://example.com/license", "https://user:secret@example.com",
                                    "https://example.com?token=private", "https://example.com#private"])
def test_music_without_valid_attribution_is_rejected_before_tts(tmp_path, monkeypatch, source):
    monkeypatch.setattr(settings, "daily_bgm_file", str(tmp_path / "missing.wav"))
    monkeypatch.setattr(settings, "daily_bgm_source", source)
    monkeypatch.setattr(remotion, "asset_for", lambda *args: None)
    monkeypatch.setattr(remotion, "synthesize", lambda *args: pytest.fail("TTS must not be called"))
    with pytest.raises(ValueError, match="HTTPS"):
        remotion.prepare([{"heading": "开场", "narration": "测试"}], "2026-10-23", tmp_path)


def test_missing_music_file_is_rejected_before_tts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_bgm_file", str(tmp_path / "missing.wav"))
    monkeypatch.setattr(settings, "daily_bgm_source", "https://example.com/license")
    monkeypatch.setattr(remotion, "asset_for", lambda *args: None)
    monkeypatch.setattr(remotion, "synthesize", lambda *args: pytest.fail("TTS must not be called"))
    with pytest.raises(ValueError, match="existing licensed local"):
        remotion.prepare([{"heading": "开场", "narration": "测试"}], "2026-10-23", tmp_path)


def test_music_is_frozen_in_production_directory(tmp_path, monkeypatch):
    original = tmp_path / "licensed.wav"
    original.write_bytes(b"original licensed music")
    output = tmp_path / "report"
    output.mkdir()
    monkeypatch.setattr(settings, "daily_bgm_file", str(original))
    monkeypatch.setattr(settings, "daily_bgm_source", "https://example.com/license")
    monkeypatch.setattr(audio, "normalize_voice", lambda *args, **kwargs: {"target_lufs": -26})
    result = audio.prepare_music(output, runner=lambda args: json.dumps(media_data()))
    original.write_bytes(b"changed after production")
    assert (output / result["original_file"]).read_bytes() == b"original licensed music"
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize("changes", [{"width": 720}, {"height": 1280},
                                     {"avg_frame_rate": "25/1"}, {"duration": "3.8"},
                                     {"codec_name": "vp9"}, {"pix_fmt": "yuv444p"}])
def test_inspection_rejects_wrong_picture_or_timeline(tmp_path, changes):
    with pytest.raises(RuntimeError):
        audio.validate_video(tmp_path / "video.mp4", 4,
                             runner=lambda args: json.dumps(media_data(**changes)))


def test_inspection_rejects_missing_audio(tmp_path):
    data = media_data()
    data["streams"].pop()
    with pytest.raises(RuntimeError, match="one picture and one audio"):
        audio.validate_video(tmp_path / "video.mp4", 4, runner=lambda args: json.dumps(data))


def test_master_uses_ducking_and_copies_video_without_reencoding(tmp_path, monkeypatch):
    (tmp_path / "video.mp4").write_bytes(b"rendered")
    (tmp_path / "music-normalized.wav").write_bytes(b"music")
    calls = []
    monkeypatch.setattr(audio, "validate_video", lambda *args, **kwargs: {"verified": True})
    monkeypatch.setattr(audio, "normalize_voice", lambda *args, **kwargs: {"target_lufs": -16})

    def execute(args):
        calls.append(args)
        if "-f" in args:
            return json.dumps(loudness(input_i="-16.0", input_tp="-1.4"))
        Path(args[-1]).write_bytes(b"mastered")
        return ""

    music = {"file": "music-normalized.wav", "original_file": "music-source.wav",
             "source": "https://example.com/license"}
    result = audio.master_video(tmp_path, 4, music=music, runner=execute)
    filters = calls[0][calls[0].index("-filter_complex") + 1]
    assert "sidechaincompress=" in filters
    assert "afade=t=in" in filters and "afade=t=out" in filters
    assert calls[1][calls[1].index("-c:v") + 1] == "copy"
    assert calls[1][calls[1].index("-t") + 1] == "4"
    assert (tmp_path / "video.mp4").read_bytes() == b"mastered"
    assert result["bgm"]["ducking"] == "sidechaincompress"


def test_master_rejects_encoded_peak_and_preserves_original_video(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"rendered")
    monkeypatch.setattr(audio, "validate_video", lambda *args, **kwargs: {"verified": True})
    monkeypatch.setattr(audio, "normalize_voice", lambda *args, **kwargs: {"target_lufs": -16})

    def execute(args):
        if "-f" in args:
            return json.dumps(loudness(input_i="-16.0", input_tp="-0.8"))
        Path(args[-1]).write_bytes(b"mastered")
        return ""

    with pytest.raises(RuntimeError, match="true-peak verification"):
        audio.master_video(tmp_path, 4, runner=execute)
    assert video.read_bytes() == b"rendered"
    assert not (tmp_path / "video-mastered.mp4").exists()


def test_master_failure_removes_ready_result_and_marks_progress_failed(tmp_path, monkeypatch):
    renderer = tmp_path / "renderer"
    (renderer / "node_modules/remotion").mkdir(parents=True)
    (renderer / "node_modules/remotion/package.json").write_text("{}")
    monkeypatch.setattr(remotion, "RENDERER_DIR", renderer)
    monkeypatch.setattr(remotion.shutil, "which", lambda args: "node")
    monkeypatch.setattr(remotion, "ensure_tools", lambda: None)
    monkeypatch.setattr(remotion, "prepare", lambda *args: {"scenes": [{"durationInFrames": 120}]})

    def render(directory):
        (directory / "render-raw-result.json").write_text(json.dumps({"duration_seconds": 4}))

    def fail(*args, **kwargs):
        assert not (tmp_path / "render-result.json").exists()
        assert json.loads((tmp_path / "render-progress.json").read_text())["phase"] == "mastering"
        raise RuntimeError("verification failed")

    monkeypatch.setattr(remotion, "invoke_renderer", render)
    monkeypatch.setattr(remotion, "master_video", fail)
    with pytest.raises(RuntimeError, match="verification failed"):
        remotion.render([], "2026-10-23", tmp_path)
    assert not (tmp_path / "render-result.json").exists()
    assert json.loads((tmp_path / "render-progress.json").read_text())["phase"] == "failed"


def test_ffmpeg_process_failure_hides_commands_and_private_output(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args, 1, stdout=b"private filename", stderr=b"provider-secret"))
    with pytest.raises(RuntimeError) as error:
        audio.run(["ffmpeg", "private filename"])
    assert "private filename" not in str(error.value)
    assert "provider-secret" not in str(error.value)


@pytest.mark.skipif(not (shutil.which(settings.daily_ffmpeg_command)
                        and shutil.which(settings.daily_ffprobe_command)),
                    reason="FFmpeg/ffprobe not installed")
@pytest.mark.parametrize("with_music", [False, True])
def test_real_two_pass_master_retains_video_packets_and_sync(tmp_path, monkeypatch, with_music):
    """真实编码验收：两遍响度、AAC 交付、视频包哈希与时间轴，不调用付费接口。"""
    video = tmp_path / "video.mp4"
    audio.run([settings.daily_ffmpeg_command, "-y", "-v", "error", "-f", "lavfi", "-i",
               "color=c=black:s=1080x1920:r=30:d=4", "-f", "lavfi", "-i",
               "sine=frequency=440:sample_rate=48000:duration=4", "-c:v", "libx264",
               "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac",
               "-ar", "48000", "-ac", "2", "-t", "4", str(video)])

    def video_hash():
        return audio.run([settings.daily_ffmpeg_command, "-v", "error", "-i", str(video),
                          "-map", "0:v:0", "-c", "copy", "-f", "hash", "-"]).strip()

    previous = video_hash()
    music = None
    if with_music:
        original = tmp_path / "licensed.wav"
        audio.run([settings.daily_ffmpeg_command, "-y", "-v", "error", "-f", "lavfi", "-i",
                   "sine=frequency=220:sample_rate=48000:duration=2", str(original)])
        monkeypatch.setattr(settings, "daily_bgm_file", str(original))
        monkeypatch.setattr(settings, "daily_bgm_source", "https://example.com/local-test-license")
        music = audio.prepare_music(tmp_path)
    result = audio.master_video(tmp_path, 4, music=music)
    assert result["media"]["verified"] is True
    assert abs(result["encoded_lufs"] + 16) <= 0.6
    assert result["encoded_true_peak_dbtp"] <= -1
    assert video_hash() == previous
    assert (tmp_path / "audio.m4a").stat().st_size > 1000
    assert bool(result["bgm"]) == with_music
