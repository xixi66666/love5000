"""FFmpeg 音频母带：实测双遍响度、授权配乐混音与成片验收。"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import settings

Runner = Callable[[list[str]], str]
SAMPLE_RATE = 48_000
TARGET_LUFS = -16.0
TRUE_PEAK = -1.0


def ensure_tools(*, runner: Runner | None = None) -> None:
    """在付费合成之前检测工具与本流程必需的音频滤镜。"""
    execute = runner or run
    filters = execute([settings.daily_ffmpeg_command, "-hide_banner", "-filters"])
    if any(name not in filters for name in ("loudnorm", "sidechaincompress", "amix")):
        raise RuntimeError("FFmpeg requires loudnorm, sidechaincompress and amix audio filters")
    execute([settings.daily_ffprobe_command, "-version"])


def run(args: list[str]) -> str:
    """loudnorm 在 stderr 输出测量值；只用于无子进程的 FFmpeg/ffprobe。"""
    try:
        process = subprocess.run(args, capture_output=True, check=False,
                                 timeout=settings.daily_render_timeout_seconds)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Audio processing unavailable or timed out; check FFmpeg tools") from None
    if process.returncode:
        # 不回显本地路径、来源 URL、FFmpeg 原始错误或命令行。
        raise RuntimeError("Audio processing failed; check media and FFmpeg installation")
    return process.stdout.decode("utf-8", "replace") + process.stderr.decode("utf-8", "replace")


def probe(path: Path, *, runner: Runner = run) -> dict:
    try:
        result = json.loads(runner([
            settings.daily_ffprobe_command, "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ]))
        if not isinstance(result, dict):
            raise TypeError()
        return result
    except (ValueError, TypeError):
        raise RuntimeError("Media inspection returned invalid metadata") from None


def _number(value: object) -> float:
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise RuntimeError("Media measurement is missing or invalid") from None


def _measurement(output: str) -> dict:
    # 不解析或持久化 FFmpeg 前面的诊断文本，其中可能含私有路径。
    for start in reversed([i for i, character in enumerate(output) if character == "{"]):
        try:
            result, _ = json.JSONDecoder().raw_decode(output[start:])
            if "input_i" in result:
                for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
                    _number(result[key])
                return result
        except (ValueError, TypeError, KeyError):
            continue
    raise RuntimeError("No finite loudness measurement; silent or invalid audio cannot be mastered")


def normalize_voice(source: Path, target: Path, *, runner: Runner = run,
                    target_lufs: float = TARGET_LUFS, true_peak: float = TRUE_PEAK) -> dict:
    """先测量再带入 measured_* 参数，处理期间不改变语速或裁剪音轨。"""
    base = [settings.daily_ffmpeg_command, "-y", "-hide_banner", "-nostats", "-i", str(source),
            "-map", "0:a:0", "-vn", "-sn", "-dn"]
    first = _measurement(runner(base + [
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:print_format=json",
        "-f", "null", "-",
    ]))
    # 将实测 LRA 纳入目标以优先采用线性增益；峰值约束需要动态处理时如实记录。
    lra = max(11.0, _number(first["input_lra"]))
    if lra > 50:
        raise RuntimeError("Audio loudness range is unsupported")
    filters = (
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:"
        f"measured_I={first['input_i']}:measured_TP={first['input_tp']}:"
        f"measured_LRA={first['input_lra']}:measured_thresh={first['input_thresh']}:"
    )
    try:
        offset = _number(first["target_offset"])
        # 强瞬态配音会触发动态限峰，FFmpeg 一次校正有时仍相差约 0.7 LU。
        # 始终从原始 PCM 重做处理，仅在实测偏差超标时再校正，避免累计有损处理。
        for processing_pass in range(1, 4):
            if abs(offset) > 99:
                raise RuntimeError("Audio gain correction is outside the supported range")
            second = _measurement(runner(base + [
                "-af", filters + f"offset={offset:g}:linear=true:print_format=json",
                "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s24le", str(target),
            ]))
            difference = target_lufs - _number(second.get("output_i"))
            if abs(difference) <= 0.5:
                break
            if second.get("normalization_type") != "dynamic":
                break
            offset += difference
        if second.get("normalization_type") not in {"linear", "dynamic"}:
            raise RuntimeError("Audio returned an unsupported loudness normalization mode")
        if abs(_number(second.get("output_i")) - target_lufs) > 0.5:
            raise RuntimeError("Audio did not reach the requested loudness target")
        if _number(second.get("output_tp")) > true_peak + 0.1:
            raise RuntimeError("Audio exceeds the requested true-peak limit")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {
        "method": "ffmpeg-loudnorm-two-pass", "normalization": second["normalization_type"],
        "target_lufs": target_lufs, "true_peak_limit_dbtp": true_peak,
        "sample_rate": SAMPLE_RATE, "input_lufs": _number(first["input_i"]),
        "processing_passes": processing_pass,
        "output_lufs": _number(second["output_i"]),
        "output_true_peak_dbtp": _number(second["output_tp"]),
    }


def prepare_music(directory: Path, *, runner: Runner = run) -> dict | None:
    """仅固化用户配置的本地授权音乐，验证失败发生在任何付费 TTS 之前。"""
    filename, source = settings.daily_bgm_file.strip(), settings.daily_bgm_source.strip()
    if not filename and not source:
        return None
    try:
        url = urlsplit(source)
        valid_source = (url.scheme == "https" and url.hostname and not url.username
                        and not url.password and not url.query and not url.fragment and len(source) <= 500)
    except ValueError:
        valid_source = False
    if not valid_source:
        raise ValueError("DAILY_BGM_SOURCE must be an HTTPS attribution without credentials")
    original = Path(filename).expanduser() if filename else None
    if original is None or not original.is_file():
        raise ValueError("DAILY_BGM_FILE must point to an existing licensed local audio file")
    if original.suffix.lower() not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
        raise ValueError("DAILY_BGM_FILE audio format is unsupported")
    copied = directory / ("music-source" + original.suffix.lower())
    try:
        shutil.copyfile(original, copied)
    except OSError:
        raise RuntimeError("Background music could not be copied to this production") from None
    metadata = probe(copied, runner=runner)
    if not any(stream.get("codec_type") == "audio" for stream in metadata.get("streams", [])):
        raise RuntimeError("Background music has no audio stream")
    duration = _number(metadata.get("format", {}).get("duration"))
    if duration < 0.4 or duration > 86_400:
        raise RuntimeError("Background music duration is unsupported")
    target = directory / "music-normalized.wav"
    normalization = normalize_voice(copied, target, runner=runner, target_lufs=-26.0)
    return {"file": target.name, "original_file": copied.name, "source": source,
            "normalization": normalization}


def validate_video(path: Path, expected_duration: float, *, runner: Runner = run) -> dict:
    """验收真实文件中的音视频流，不能只相信渲染器写出的结果 JSON。"""
    expected = _number(expected_duration)
    if expected <= 0 or expected > 7200:
        raise RuntimeError("Rendered video duration is unsupported")
    data = probe(path, runner=runner)
    videos = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"]
    audios = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise RuntimeError("Rendered video must contain one picture and one audio stream")
    video, audio = videos[0], audios[0]
    if (video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p"
            or audio.get("codec_name") != "aac"):
        raise RuntimeError("Rendered video must use H.264 yuv420p and AAC audio")
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "0")))
    except (ValueError, ZeroDivisionError):
        raise RuntimeError("Rendered video has an invalid frame rate") from None
    if (video.get("width"), video.get("height")) != (1080, 1920) or abs(fps - 30) > 0.001:
        raise RuntimeError("Rendered video must be 1080x1920 at 30 FPS")
    if _number(audio.get("sample_rate")) != SAMPLE_RATE or audio.get("channels") != 2:
        raise RuntimeError("Rendered audio must be 48 kHz stereo")
    duration = _number(data.get("format", {}).get("duration"))
    tolerance = 0.1  # 一个视频帧与 AAC 编码补齐范围，不允许长静音或截断通过。
    for actual in (duration, _number(video.get("duration")), _number(audio.get("duration"))):
        if abs(actual - expected) > tolerance:
            raise RuntimeError("Rendered audio/video duration does not match the scene timeline")
    for stream in (video, audio):
        if abs(_number(stream.get("start_time", 0))) > tolerance:
            raise RuntimeError("Rendered audio/video start times are not synchronized")
    return {"width": 1080, "height": 1920, "fps": fps, "duration_seconds": duration,
            "video_codec": "h264", "pixel_format": "yuv420p",
            "audio_sample_rate": SAMPLE_RATE, "audio_channels": 2,
            "audio_codec": audio.get("codec_name"), "verified": True}


def master_video(directory: Path, expected_duration: float, *, music: dict | None = None,
                 runner: Runner = run) -> dict:
    video = directory / "video.mp4"
    validate_video(video, expected_duration, runner=runner)
    source = video
    temporary = directory / "video-mastered.mp4"
    mixed, mastered = directory / "audio-mix.wav", directory / "audio-mastered.wav"
    try:
        if music:
            source = mixed
            duration = _number(expected_duration)
            fade_in, fade_out = min(0.8, duration / 2), min(1.2, duration / 2)
            filters = (
                "[0:a:0]asplit=2[voice][control];"
                f"[1:a:0]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={duration - fade_out}:d={fade_out}[music];"
                "[music][control]sidechaincompress=threshold=0.025:ratio=8:"
                "attack=15:release=300[ducked];"
                "[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
                f"apad=whole_dur={duration},atrim=duration={duration}[mix]"
            )
            runner([settings.daily_ffmpeg_command, "-y", "-v", "error", "-i", str(video),
                    "-stream_loop", "-1", "-i", str(directory / music["file"]),
                    "-filter_complex", filters, "-map", "[mix]", "-ar", str(SAMPLE_RATE),
                    "-ac", "2", "-c:a", "pcm_s24le", str(mixed)])
        normalization = normalize_voice(source, mastered, runner=runner, true_peak=-1.5)
        runner([settings.daily_ffmpeg_command, "-y", "-v", "error", "-i", str(video),
                "-i", str(mastered), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", "2",
                "-t", str(expected_duration), "-movflags", "+faststart", str(temporary)])
        verified = validate_video(temporary, expected_duration, runner=runner)
        # AAC 编码可能带来真峰值过冲；测量最终交付文件，超过限制即拒绝交付。
        final = _measurement(runner([
            settings.daily_ffmpeg_command, "-hide_banner", "-nostats", "-i", str(temporary),
            "-map", "0:a:0", "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
            "-f", "null", "-",
        ]))
        if abs(_number(final["input_i"]) - TARGET_LUFS) > 0.6:
            raise RuntimeError("Encoded audio failed integrated loudness verification")
        if _number(final["input_tp"]) > TRUE_PEAK:
            raise RuntimeError("Encoded audio failed true-peak verification")
        runner([settings.daily_ffmpeg_command, "-y", "-v", "error", "-i", str(temporary),
                "-vn", "-c:a", "copy", str(directory / "audio.m4a")])
        temporary.replace(video)
        return {"normalization": normalization, "encoded_lufs": _number(final["input_i"]),
                "encoded_true_peak_dbtp": _number(final["input_tp"]), "media": verified,
                "bgm": ({"source": music["source"], "file": music["original_file"],
                         "ducking": "sidechaincompress", "fade_in_seconds": fade_in,
                         "fade_out_seconds": fade_out} if music else None)}
    finally:
        for path in (temporary, mixed, mastered):
            path.unlink(missing_ok=True)
