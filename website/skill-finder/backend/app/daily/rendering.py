"""两种画面引擎共用同一套母带、实际媒体验收和就绪发布流程。"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from app.daily.progress import current


def finish_render(directory: Path, manifest: dict, *, invoke: Callable[[Path], None],
                  master: Callable, engine: str) -> float:
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
