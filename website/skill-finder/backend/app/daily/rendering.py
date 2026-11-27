"""两种画面引擎共用同一套母带、实际媒体验收和就绪发布流程。

`finish_render` 是唯一把渲染器输出提升为正式结果的关口：Node 只允许写
`render-raw-result.json`；这里核对分镜时长、更新 `render-progress.json` 的 phase、
调用母带函数复检真实音视频，最后原子发布 `render-result.json`。

失败时删除所有中间结果并把 phase 写成 `failed`，因此未通过验收的成片不会进入待
审核状态；phase 只反映实际推进到的阶段，不预估剩余帧数。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from app.daily.progress import current


def finish_render(directory: Path, manifest: dict, *, invoke: Callable[[Path], None],
                  master: Callable, engine: str) -> float:
    """把渲染器的原始输出提升为正式结果。

    顺序：清理旧结果、调用引擎、只读取 `render-raw-result.json`、核对分镜时间轴、
    把 phase 记为 mastering、调用母带函数做混音与真实音视频验收，最后原子发布
    `render-result.json`。

    Args:
        directory: 本期任务目录。
        manifest: `prepare` 写出的清单，用分镜帧数核对时长。
        invoke: 引擎调用，签名 `invoke(directory)`。
        master: 母带函数，签名 `master(directory, duration, music=...)`。
        engine: 写入结果的引擎标识，`remotion` 或 `hyperframes`。

    Returns:
        成片时长，单位秒。

    Raises:
        RuntimeError: 渲染结果与分镜时长不一致，或母带验收失败。失败时删除中间
            结果并把 phase 写成 `failed`，不会残留正式结果。
    """
    progress = current()
    if progress:
        progress.begin("render", "正在编排模板、渲染画面并编码音视频。")
    result_file = directory / "render-result.json"
    raw_file = directory / "render-raw-result.json"
    progress_file = directory / "render-progress.json"
    temporary_result = directory / ".render-result.json.tmp"
    result_file.unlink(missing_ok=True)
    raw_file.unlink(missing_ok=True)
    temporary_result.unlink(missing_ok=True)
    frame_progress = {}
    try:
        invoke(directory)
        # Node 只写临时结果；最终 ready 必须由统一的真实音视频验收发布。
        result = json.loads(raw_file.read_text(encoding="utf-8"))
        raw_file.unlink()
        expected_duration = sum(scene["durationInFrames"] for scene in manifest["scenes"]) / 30
        if abs(float(result["duration_seconds"]) - expected_duration) > 0.001:
            raise RuntimeError("Renderer result does not match the prepared scene timeline")
        if progress:
            progress.begin("render", "画面渲染完成，正在混音、制作整片母带并验收实际音视频。")
        if progress_file.is_file():
            frame_progress = json.loads(progress_file.read_text(encoding="utf-8"))
        frame_progress["phase"] = "mastering"
        progress_file.write_text(json.dumps(frame_progress), encoding="utf-8")
        result["audio_mastering"] = master(directory, expected_duration, music=manifest.get("music"))
        result["renderer"] = engine
        temporary_result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_result.replace(result_file)
    except Exception:
        result_file.unlink(missing_ok=True)
        raw_file.unlink(missing_ok=True)
        temporary_result.unlink(missing_ok=True)
        frame_progress["phase"] = "failed"
        progress_file.write_text(json.dumps(frame_progress), encoding="utf-8")
        raise
    frame_progress["phase"] = "completed"
    progress_file.write_text(json.dumps(frame_progress), encoding="utf-8")
    if progress:
        progress.finish("render", f"已生成 {result['duration_seconds']:.1f} 秒视频、音轨与封面。")
    return float(result["duration_seconds"])
