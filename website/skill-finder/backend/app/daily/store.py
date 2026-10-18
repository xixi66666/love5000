from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from filelock import FileLock

from app.core.config import settings


def root() -> Path:
    path = Path(settings.daily_reports_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_dir(day: str) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Invalid report date")
    date.fromisoformat(day)
    return root() / day


def lock() -> FileLock:
    return FileLock(str(root() / ".pipeline.lock"), timeout=0)


def load(day: str) -> dict:
    return json.loads((report_dir(day) / "report.json").read_text(encoding="utf-8"))


def save(report: dict) -> None:
    directory = report_dir(report["date"])
    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / "report.json.tmp"
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(directory / "report.json")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def approval_digest(report: dict) -> str:
    """Bind approval to the video, script, title and caption the reviewer saw."""
    body = {key: report.get(key) for key in ("video_sha256", "script", "title", "caption")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_approval(report: dict) -> bool:
    video = report_dir(report["date"]) / "video.mp4"
    return (
        report.get("status") == "approved"
        and report.get("approved_digest") == approval_digest(report)
        and video.is_file()
        and digest(video) == report.get("video_sha256")
    )
