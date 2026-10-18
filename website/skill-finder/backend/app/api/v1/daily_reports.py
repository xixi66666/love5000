from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from filelock import Timeout
from pydantic import BaseModel, Field

from app.api.dependencies import require_admin_key
from app.core.config import settings
from app.daily import store
from app.daily.douyin_login import private_dir
from app.daily.pipeline import now

router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])
FILES = {"video.mp4", "audio.m4a", "poster.png", "report.md", "script.txt", "subtitles.srt"}


def require_daily_admin(request: Request, _: None = Depends(require_admin_key)) -> None:
    if request.url.scheme != "https" and request.url.hostname not in {
        "127.0.0.1", "localhost", "::1",
    }:
        raise HTTPException(403, "Use HTTPS or an SSH tunnel for daily report administration")


class Review(BaseModel):
    decision: Literal["approve", "reject"]
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def read(day: str) -> dict:
    try:
        return store.load(day)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Report not found") from None


async def task(action: str, day: str | None = None) -> None:
    args = [sys.executable, "-m", "app.daily.cli", action]
    if action == "generate":
        args.append("--collect")
    if day:
        args += ["--date", day]
    process = await asyncio.create_subprocess_exec(*args)
    await process.wait()


@router.get("")
def list_reports() -> dict:
    reports = []
    for path in sorted(store.root().glob("????-??-??/report.json"), reverse=True)[:90]:
        try:
            reports.append(store.load(path.parent.name))
        except (ValueError, OSError):
            continue
    return {
        "items": reports, "timezone": settings.business_timezone,
        "qq_configured": bool(settings.daily_qq_target and settings.daily_openclaw_command),
        "douyin_configured": (
            settings.douyin_publish_enabled and Path(settings.douyin_storage_state).is_file()
        ),
    }


@router.post("/publisher/login", status_code=202, dependencies=[Depends(require_daily_admin)])
async def start_login(background: BackgroundTasks) -> dict:
    try:
        with store.lock():
            pass
    except Timeout:
        raise HTTPException(409, "Another daily task is running; retry after it finishes") from None
    background.add_task(task, "login")
    return {"status": "accepted"}


@router.get("/publisher/login", dependencies=[Depends(require_daily_admin)])
def login_status() -> dict:
    try:
        return json.loads((private_dir() / "login-status.json").read_text())
    except FileNotFoundError:
        return {"status": "not_started"}


@router.get("/publisher/login/screen", dependencies=[Depends(require_daily_admin)])
def login_screen():
    path = private_dir() / "login-screen.png"
    if not path.is_file():
        raise HTTPException(404, "Login screen is not ready")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.post("/generate", status_code=202, dependencies=[Depends(require_daily_admin)])
async def generate_report(background: BackgroundTasks) -> dict:
    background.add_task(task, "generate")
    return {"status": "accepted"}


@router.get("/{day}")
def get_report(day: str) -> dict:
    return read(day)


@router.get("/{day}/files/{filename}")
def get_file(day: str, filename: str):
    report = read(day)
    if filename not in FILES or report.get("status") in {"generating", "failed"}:
        raise HTTPException(404, "Artifact is not ready")
    path = store.report_dir(day) / filename
    if not path.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(path, filename=filename if filename != "video.mp4" else None)


@router.post("/{day}/review", dependencies=[Depends(require_daily_admin)])
def review_report(day: str, body: Review, background: BackgroundTasks) -> dict:
    try:
        with store.lock():
            report = read(day)
            if report.get("status") != "pending_review":
                raise HTTPException(409, "This report is not awaiting review")
            video = store.report_dir(day) / "video.mp4"
            if (
                store.approval_digest(report) != body.expected_digest
                or not video.is_file()
                or store.digest(video) != report.get("video_sha256")
            ):
                raise HTTPException(409, "Content changed; reload and review the current video")
            report.update(
                status="approved" if body.decision == "approve" else "rejected",
                reviewed_at=now(),
            )
            if body.decision == "approve":
                report["approved_digest"] = body.expected_digest
            store.save(report)
    except Timeout:
        raise HTTPException(409, "Another daily task is running; retry later") from None
    if body.decision == "approve":
        background.add_task(task, "publish", day)
    return report


@router.post("/{day}/publish", status_code=202, dependencies=[Depends(require_daily_admin)])
async def publish_report(day: str, background: BackgroundTasks) -> dict:
    if not store.verify_approval(read(day)):
        raise HTTPException(409, "Approve the current video before publishing")
    background.add_task(task, "publish", day)
    return {"status": "accepted"}
