"""FFmpeg 音频母带：实测双遍响度、授权配乐混音与成片验收。

对外入口按流水线顺序为 `ensure_tools`（在任何付费 TTS 之前检查 ffmpeg 滤镜与
ffprobe）、`prepare_music`（固化本地授权配乐并预先归一）、`normalize_voice`
（两遍 loudnorm）、`master_video`（混音、重编码 AAC、再验收）。

外部二进制：`ffmpeg`（loudnorm / sidechaincompress / amix / afade / apad）与
`ffprobe`（读取流信息），命令来自 `settings.daily_ffmpeg_command` 与
`settings.daily_ffprobe_command`。子进程输出只在内存里解析，不落盘、不回显路径、
URL 或原始错误；任一步失败统一抛 `RuntimeError`，绝不交付未经复检的成片。
"""
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
    """读取 ffprobe 的流与容器元数据。

    Args:
        path: 待检查的本地媒体文件。
        runner: 可注入的子进程执行器，测试用它替代真实 ffprobe。

    Returns:
        解析后的字典，保留 ffprobe 原始字段名。

    Raises:
        RuntimeError: 输出不是 JSON 对象，通常是工具缺失、文件损坏或版本不支持。
    """
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
    """把 loudnorm 或 ffprobe 的测量值转成有限浮点数。

    Raises:
        RuntimeError: 缺失、非数字或 NaN/Inf；这类值无法参与增益校正。
    """
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise RuntimeError("Media measurement is missing or invalid") from None


def _measurement(output: str) -> dict:
    """从 loudnorm 的诊断输出里取出测量 JSON。

    loudnorm 把 JSON 混在 stderr 文本末尾，前面的日志可能包含私有路径，因此从最后
    一个 `{` 开始反向尝试解析，只接受含 `input_i` 且各测量值有限的片段。

    Raises:
        RuntimeError: 拿不到可用测量值，例如音轨静音或格式不受支持。
    """
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
    """按实测两遍 loudnorm 把语音或整片音轨归一到目标响度。

    第一遍只测量，第二遍把 `measured_*` 带入并优先走线性增益；强瞬态会落到动态
    限峰，此时最多再校正三次 offset，且每次都从原始 PCM 重做，避免累计有损处理。
    全程不改变语速、不裁剪音轨。

    Args:
        source: 输入音频或视频，取第一条 `0:a:0`。
        target: 输出 48 kHz 双声道 PCM 24-bit WAV；校验失败时会被删除。
        runner: 可注入的执行器。
        target_lufs: 目标整合响度，语音为 -16 LUFS。
        true_peak: 真峰值上限，单位 dBTP。

    Returns:
        母带参数与实测值：方法、normalization 类型、处理遍数、输入/输出响度与
        真峰值。

    Raises:
        RuntimeError: 响度范围超过 50 LU、增益偏移超出支持范围、未达到目标响度或
            超过真峰值上限。
    """
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
    """把用户配置的本地授权配乐固化到本期目录并预先归一。

    必须在任何付费 TTS 之前调用：配乐来源、文件或格式不合法时尽早失败，不浪费
    配音额度。只复制本地文件，不会下载 `DAILY_BGM_SOURCE`。

    Args:
        directory: 本期任务目录，配乐复制为 `music-source<后缀>`。
        runner: 可注入的执行器。

    Returns:
        含 `file`、`original_file`、`source` 与母带参数的字典；未配置配乐时返回
        `None`。

    Raises:
        ValueError: 来源不是无凭据的 HTTPS 地址、文件不存在或格式不支持。
        RuntimeError: 复制失败、没有音频流、时长超出 0.4 到 86400 秒或归一失败。
    """
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
    """验收真实文件中的音视频流，不能只相信渲染器写出的结果 JSON。

    逐项校验流数量、编码（H.264 yuv420p 加 AAC）、分辨率 1080×1920、30 FPS、
    48 kHz 双声道、容器与两路 stream 的时长，以及起始时间是否同步。

    Args:
        path: 渲染器产出的 `video.mp4`。
        expected_duration: 分镜时间轴总时长，用于逐项比对。
        runner: 可注入的执行器。

    Returns:
        验收通过的媒体参数：宽高、帧率、时长、编码、采样率与声道数。

    Raises:
        RuntimeError: 任一硬性条件不满足；调用方据此拒绝交付。
    """
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
    """混音、重编码并复检最终成片。

    顺序：先 `validate_video` 验证渲染结果；有配乐时用侧链压缩让人声压过音乐
    （淡入淡出各不超过片长一半）；归一语音或混音；重新封装 H.264 与 AAC；再验收
    一遍；最后对**已编码**文件测响度与真峰值，AAC 过冲超限即拒绝交付。

    Args:
        directory: 本期任务目录，成片原地替换 `video.mp4` 并导出 `audio.m4a`。
        expected_duration: 期望总时长，单位秒。
        music: `prepare_music` 的返回值；`None` 表示纯人声。
        runner: 可注入的执行器。

    Returns:
        母带参数、编码后实测响度与真峰值、成片验收参数，以及配乐混音信息。

    Raises:
        RuntimeError: 任一步骤失败或复检不达标；中间文件在 finally 中清理。
    """
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
