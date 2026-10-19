from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from filelock import FileLock, Timeout
from pydantic import BaseModel, Field

from app.api.dependencies import require_admin_key
from app.core.config import settings
from app.daily import store
from app.daily.douyin_login import private_dir
from app.daily.pipeline import now
from app.daily.progress import Tracker

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


async def generation_task(lease: FileLock, day: str) -> None:
    try:
        await task("generate")
        progress = Tracker(day)
        if progress.data["state"] == "queued":
            progress.fail(RuntimeError("Task did not start"))
    except Exception as error:  # noqa: BLE001 - 后台边界只记录脱敏错误类别
        Tracker(day).fail(error)
    finally:
        lease.release()


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


@router.get("/console")
def get_console(day: str | None = None) -> dict:
    from app.daily.console import snapshot

    try:
        return snapshot(day or now()[:10])
    except ValueError:
        raise HTTPException(422, "Invalid report date") from None


@router.get("/samples/{sample}/files/{filename}")
def sample_file(sample: str, filename: str):
    if not re.fullmatch(r"\d{8}-\d{6}", sample) or filename not in {
        "video.mp4", "audio.m4a", "poster.png", "subtitles.srt",
    }:
        raise HTTPException(404, "Sample artifact not found")
    root = (store.root().parent / "video-samples").resolve()
    path = (root / sample / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Sample artifact not found")
    return FileResponse(path)


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
    day = now()[:10]
    lease = FileLock(str(store.root() / ".dispatch.lock"), timeout=0, thread_local=False)
    try:
        lease.acquire()
        with store.lock():
            try:
                existing = store.load(day)
            except FileNotFoundError:
                existing = {}
            if existing.get("status") in {
                "pending_review", "approved", "rejected", "publishing", "published", "publish_unknown",
            }:
                raise HTTPException(409, "Today's report has reached review and cannot be overwritten")
            progress = Tracker(day, reset=True)
            progress.data.update(state="queued", current="collection")
            progress.set("collection", "queued", "任务已接受，等待制作进程启动。")
    except Timeout:
        lease.release()
        raise HTTPException(409, "Another daily task is running; retry after it finishes") from None
    except Exception:
        lease.release()
        raise
    background.add_task(generation_task, lease, day)
    return {"status": "accepted", "date": day}


@router.put("/{day}/assets/{owner}/{repo}", dependencies=[Depends(require_daily_admin)])
async def upload_asset(day: str, owner: str, repo: str, request: Request,
                       filename: str = Query(max_length=200), source: str = Query(max_length=500)) -> dict:
    from app.daily.assets import receive

    report = read(day)
    if owner + "/" + repo not in {item["full_name"] for item in report.get("items", [])}:
        raise HTTPException(422, "Project is not part of this report")
    try:
        with store.lock():
            return await receive(request, owner, repo, filename, source)
    except Timeout:
        raise HTTPException(409, "Wait for the current task to finish before changing source assets") from None


@router.post("/{day}/notify", status_code=202, dependencies=[Depends(require_daily_admin)])
async def notify_report(day: str, background: BackgroundTasks) -> dict:
    if read(day).get("status") not in {"pending_review", "approved", "published"}:
        raise HTTPException(409, "Report is not ready for delivery")
    if not (settings.daily_qq_target and settings.daily_openclaw_command):
        raise HTTPException(409, "QQ delivery is not configured")
    background.add_task(task, "notify", day)
    return {"status": "accepted"}


@router.get("/{day}")
def get_report(day: str) -> dict:
    return read(day)


@router.get("/{day}/files/{filename}")
def get_file(day: str, filename: str):
    report = read(day)
    if filename not in FILES or (report.get("status") in {"generating", "failed"}
                                 and filename not in {"script.txt", "report.md"}):
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
            progress = Tracker(day)
            progress.set("review", "completed" if body.decision == "approve" else "rejected",
                         "已批准当前视频和发布文案。" if body.decision == "approve" else "已退回当前版本，不会发布。")
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
