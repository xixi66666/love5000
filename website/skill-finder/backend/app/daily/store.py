"""日报任务目录、全局锁与人工批准凭据。

所有路径都由 `settings.daily_reports_dir`（默认 `data/daily-reports`）推导，
`report_dir` 严格校验日期格式以防目录穿越。`lock` 返回超时为 0 的排他 `FileLock`，
生成、通知、发布与登录都靠它串行化；拿不到锁时调用方立即失败而不是排队等待。

`approval_digest` 把 `video_sha256`、口播、标题和文案绑成一个摘要，
`verify_approval` 在发布前重新计算并比对，确保审核者看到的版本就是提交的版本。
报告与产物属于私有运行数据，不得出现在日志或响应中。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from filelock import FileLock

from app.core.config import settings


def root() -> Path:
    """返回并确保日报根目录存在（`settings.daily_reports_dir`）。"""
    path = Path(settings.daily_reports_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_dir(day: str) -> Path:
    """返回某天的任务目录；只校验格式，不创建目录。

    Raises:
        ValueError: 日期不是 `YYYY-MM-DD` 或不是真实日期，防止拼出目录穿越路径。
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Invalid report date")
    date.fromisoformat(day)
    return root() / day


def lock() -> FileLock:
    """返回超时为 0 的排他文件锁，用于串行化生成、通知、发布与登录。

    拿不到锁会立刻抛 `filelock.Timeout`，由调用方按“另一个任务正在跑”处理，
    不在这里排队等待。
    """
    return FileLock(str(root() / ".pipeline.lock"), timeout=0)


def load(day: str) -> dict:
    """读取某天的 `report.json`。

    Raises:
        FileNotFoundError: 当天还没有报告；调用方用它区分“未开始”和“读坏了”。
    """
    return json.loads((report_dir(day) / "report.json").read_text(encoding="utf-8"))


def save(report: dict) -> None:
    """原子写入 `report.json`（先写 `.tmp` 再替换），避免读到半份报告。"""
    directory = report_dir(report["date"])
    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / "report.json.tmp"
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(directory / "report.json")


def digest(path: Path) -> str:
    """计算文件的 SHA-256，用于把批准绑定到具体视频字节。"""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def approval_digest(report: dict) -> str:
    """把批准绑定到审核者当时看到的视频、口播、标题与文案。

    Returns:
        64 位十六进制 SHA-256；参与计算的字段固定为 `video_sha256`、`script`、
        `title`、`caption`，按 key 排序后序列化，任何一项变动都会改变摘要。
    """
    body = {key: report.get(key) for key in ("video_sha256", "script", "title", "caption")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_approval(report: dict) -> bool:
    """确认“现在这份视频”就是审核者批准的那一份。

    三个条件同时成立才为真：报告状态为 `approved`、`approved_digest` 与按当前字段
    重新计算的摘要一致、`video.mp4` 存在且 SHA-256 等于记录的 `video_sha256`。
    任一不满足都返回假，发布流程据此拒绝提交。
    """
    video = report_dir(report["date"]) / "video.mp4"
    return (
        report.get("status") == "approved"
        and report.get("approved_digest") == approval_digest(report)
        and video.is_file()
        and digest(video) == report.get("video_sha256")
    )
