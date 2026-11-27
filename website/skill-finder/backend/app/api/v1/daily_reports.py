"""云端日报端点（``/api/v1/daily-reports``）。

浏览接口（列表、单日详情、成品文件、样片、制作操作台快照）公开只读；
管理接口（生成、审核、发布、抖音登录、素材上传、QQ 通知）要求 ``X-Admin-Key``，
并由 :func:`require_daily_admin` 额外限制为 HTTPS 或本机回环连接。

长耗时动作（生成、发布、登录）都以子进程方式跑 ``app.daily.cli``，接口只回 202，
进度写进任务目录由操作台轮询读取。发布必须绑定人工审核过的具体视频摘要：
未批准不发布，摘要不匹配不发布，结果不确定（``publish_unknown``）不自动重发。
"""
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
# 允许通过 /files/{filename} 下载的成品白名单；不在此集合内一律 404，避免读任意文件。
FILES = {"video.mp4", "audio.m4a", "poster.png", "report.md", "script.txt", "subtitles.srt"}


def require_daily_admin(request: Request, _: None = Depends(require_admin_key)) -> None:
    """管理接口的组合鉴权：先 ``X-Admin-Key``，再限制来源传输方式。

    密钥校验交给 :func:`app.api.dependencies.require_admin_key`；这里额外要求请求
    走 HTTPS 或来自本机回环地址，防止密钥经明文网络传输。生产环境通过 Nginx 终结
    TLS，本机调试则走 127.0.0.1 或 SSH 隧道。

    Args:
        request: 当前请求，用于读取 scheme 与 hostname。
        _: 密钥校验依赖，仅用于触发鉴权。

    Raises:
        HTTPException: 非 HTTPS 且非本机来源时返回 403。
    """
    if request.url.scheme != "https" and request.url.hostname not in {
        "127.0.0.1", "localhost", "::1",
    }:
        raise HTTPException(403, "Use HTTPS or an SSH tunnel for daily report administration")


class Review(BaseModel):
    """审核请求体。

    ``expected_digest`` 是审核页面当时算出的审批摘要（64 位十六进制）。服务端会和
    当前报告重新计算的摘要比对，不一致就拒绝，避免用户批准的是旧视频而发布的是新视频。
    """

    decision: Literal["approve", "reject"]
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def read(day: str) -> dict:
    """读取某一天的 ``report.json``。

    该函数同时充当日期校验：``store.load`` 对非法日期抛 ``ValueError``，
    两种失败都折叠成 404，避免把私有目录结构或真实路径写进响应。

    Args:
        day: ``YYYY-MM-DD`` 形式的业务日期。

    Returns:
        报告字典（状态、项目列表、文案、审批摘要等）。

    Raises:
        HTTPException: 报告不存在、日期格式非法或文件损坏时返回 404。
    """
    try:
        return store.load(day)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Report not found") from None


async def task(action: str, day: str | None = None) -> None:
    """以子进程方式执行一次日报 CLI 动作。

    使用当前解释器（``sys.executable``）和模块形式 ``-m app.daily.cli``，因此继承
    服务进程的环境变量与私有配置；``generate`` 会附带 ``--collect`` 先采集榜单。
    这里只等待进程退出，不检查退出码——真实状态由任务目录里的进度与报告状态表达，
    以免把子进程的非零退出误判成“接口失败”。

    Args:
        action: CLI 子命令（如 ``generate`` / ``publish`` / ``notify`` / ``login``）。
        day: 可选业务日期，缺省时由 CLI 自行按业务时区决定。
    """
    args = [sys.executable, "-m", "app.daily.cli", action]
    if action == "generate":
        args.append("--collect")
    if day:
        args += ["--date", day]
    process = await asyncio.create_subprocess_exec(*args)
    await process.wait()


async def generation_task(lease: FileLock, day: str) -> None:
    """后台生成任务的包装：兜底进度状态并保证释放派发锁。

    正常路径下子进程会自己把进度推进到终态；若子进程没启动起来（进度仍停在
    ``queued``），这里补一个失败状态，让操作台不会一直转圈。
    异常只写入脱敏的错误类别，不把堆栈或私有路径暴露到页面。

    Args:
        lease: :func:`generate_report` 抢到的 ``.dispatch.lock``，必须在 finally 释放。
        day: 本次生成的业务日期。
    """
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
    """列出最近 90 天的日报。

    请求：``GET /api/v1/daily-reports``。
    响应：``{"items": [...], "timezone": ..., "qq_configured": ..., "douyin_configured": ...}``。
    单个报告解析失败会被跳过而不是让整个列表 500；``qq_configured`` /
    ``douyin_configured`` 只表达“是否具备配置”，不代表已经送达或发布。
    """
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
    """返回一键制作操作台的状态快照。

    请求：``GET /api/v1/daily-reports/console?day=YYYY-MM-DD``，缺省为今天。
    响应：各步骤状态、计数与脱敏错误；历史任务没有工作流记录时明确标注，
    不补造进度。

    Raises:
        HTTPException: 日期格式非法时 422（只读接口，不涉及私有路径）。
    """
    from app.daily.console import snapshot

    try:
        return snapshot(day or now()[:10])
    except ValueError:
        raise HTTPException(422, "Invalid report date") from None


@router.get("/samples/{sample}/files/{filename}")
def sample_file(sample: str, filename: str):
    """下载一次样片产物（供操作台内联播放/预览）。

    请求：``GET /api/v1/daily-reports/samples/{sample}/files/{filename}``。
    响应：文件流；``sample`` 必须是 ``YYYYMMDD-HHMMSS``，文件名限定在样片白名单内，
    解析后必须仍位于 ``video-samples`` 目录中（路径穿越防护）。

    Raises:
        HTTPException: 标识或文件名不合规、文件不存在时统一 404。
    """
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
    """启动抖音扫码登录子进程。

    请求：``POST /api/v1/daily-reports/publisher/login``，无请求体。
    响应：202 ``{"status": "accepted"}``；登录进度写进私有目录的 ``login-status.json``。

    先用 ``store.lock()`` 立即抢放一次，确认没有日报任务在跑：登录会写浏览器状态文件，
    与生成/发布并发可能互相覆盖。

    Raises:
        HTTPException: 有任务正在运行时 409，提示稍后重试。
    """
    try:
        with store.lock():
            pass
    except Timeout:
        raise HTTPException(409, "Another daily task is running; retry after it finishes") from None
    background.add_task(task, "login")
    return {"status": "accepted"}


@router.get("/publisher/login", dependencies=[Depends(require_daily_admin)])
def login_status() -> dict:
    """读取抖音登录进度。

    请求：``GET /api/v1/daily-reports/publisher/login``。
    响应：私有 ``login-status.json`` 的内容；从未启动过登录时返回
    ``{"status": "not_started"}``，不把“未登录”谎报成“已登录”。
    """
    try:
        return json.loads((private_dir() / "login-status.json").read_text())
    except FileNotFoundError:
        return {"status": "not_started"}


@router.get("/publisher/login/screen", dependencies=[Depends(require_daily_admin)])
def login_screen():
    """返回抖音登录二维码的当前截屏。

    请求：``GET /api/v1/daily-reports/publisher/login/screen``。
    响应：PNG 文件流，禁用缓存（二维码会过期）。

    Raises:
        HTTPException: 截屏还没生成时返回 404。
    """
    path = private_dir() / "login-screen.png"
    if not path.is_file():
        raise HTTPException(404, "Login screen is not ready")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.post("/generate", status_code=202, dependencies=[Depends(require_daily_admin)])
async def generate_report(background: BackgroundTasks) -> dict:
    """一键生成本期日报（采集 → 筛选 → 脚本 → 配音 → 字幕 → 渲染）。

    请求：``POST /api/v1/daily-reports/generate``，无请求体；日期由服务端按业务时区取今天。
    响应：202 ``{"status": "accepted", "date": "YYYY-MM-DD"}``。

    先抢 ``.dispatch.lock``（非阻塞）确保同一时刻只有一个生成任务，再在
    ``store.lock()`` 内检查当天报告状态：已经进入审核/批准/发布等阶段时拒绝覆盖，
    避免把人工审过的成片冲掉。随后把进度置为 ``queued`` 并把锁句柄交给后台任务，
    由它在 finally 释放——因此本函数在异常分支里也必须先释放锁再抛出。

    Raises:
        HTTPException: 409 已有任务在跑或当天报告已进入审核之后的状态。
    """
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
    """上传本期某个项目的演示素材（原始文件作为请求体）。

    请求：``PUT /api/v1/daily-reports/{day}/assets/{owner}/{repo}?filename=&source=``，
    body 为 MP4/PNG/JPEG 原始字节（由 ``app.daily.assets.receive`` 校验大小与来源）。
    响应：``receive`` 返回的素材记录（文件名、大小、来源）。

    Args:
        day: 目标日期，必须已有该日报告。
        owner: 仓库所有者，与 ``repo`` 一起必须出现在本期报告的项目列表中。
        repo: 仓库名。
        request: 原始请求体来源。
        filename: 原始文件名，最长 200 字符。
        source: 素材来源 URL，最长 500 字符，必须是 HTTPS 来源。

    Raises:
        HTTPException: 404 报告不存在；422 项目不属于本期报告；409 有任务在跑
            （用 ``store.lock()`` 串行化素材写入）。
    """
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
    """通过 OpenClaw 把已完成的日报推送到 QQ（可选能力）。

    请求：``POST /api/v1/daily-reports/{day}/notify``，无请求体。
    响应：202 ``{"status": "accepted"}``。

    Raises:
        HTTPException: 409 报告还没到可投递状态，或 QQ 目标与 OpenClaw 命令未配置。
    """
    if read(day).get("status") not in {"pending_review", "approved", "published"}:
        raise HTTPException(409, "Report is not ready for delivery")
    if not (settings.daily_qq_target and settings.daily_openclaw_command):
        raise HTTPException(409, "QQ delivery is not configured")
    background.add_task(task, "notify", day)
    return {"status": "accepted"}


@router.get("/{day}")
def get_report(day: str) -> dict:
    """返回某一日的完整报告 JSON。

    请求：``GET /api/v1/daily-reports/{day}``。
    响应：报告字典（状态、项目、文案、审批摘要、时间戳）；不存在时 404。
    """
    return read(day)


@router.get("/{day}/files/{filename}")
def get_file(day: str, filename: str):
    """下载本期产物（视频、音频、封面、文案、字幕）。

    请求：``GET /api/v1/daily-reports/{day}/files/{filename}``。
    响应：文件流；``video.mp4`` 不附带下载文件名，便于浏览器内联播放。

    生成中或生成失败时只放行 ``script.txt`` 与 ``report.md``，避免页面拿到半成品视频。

    Raises:
        HTTPException: 文件名不在白名单、当前状态不允许、文件不存在时返回 404。
    """
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
    """人工审核本期成片：批准或退回。

    请求：``POST /api/v1/daily-reports/{day}/review``，体为 :class:`Review`。
    响应：更新后的报告字典。

    只有 ``pending_review`` 状态可审；批准前会同时校验审批摘要与 ``video.mp4`` 的
    SHA-256，任一不匹配就要求重新加载页面，防止“审的是旧片、发的是新片”。
    批准会写入 ``approved_digest`` 并在响应返回后触发后台发布；退回只记录状态，
    不会发布也不删除成片。全部写操作在 ``store.lock()`` 内完成。

    Raises:
        HTTPException: 409 状态不对、内容已变化或有其他任务在运行。
    """
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
    """重新触发发布（已批准或需重试的场景）。

    请求：``POST /api/v1/daily-reports/{day}/publish``，无请求体。
    响应：202 ``{"status": "accepted"}``。

    发布前再次用 ``store.verify_approval`` 校验审批摘要与视频摘要仍然匹配；
    结果不确定（``publish_unknown``）的报告不会被本接口自动重发，需要人工确认。

    Raises:
        HTTPException: 409 当前视频尚未通过审核或内容已变化。
    """
    if not store.verify_approval(read(day)):
        raise HTTPException(409, "Approve the current video before publishing")
    background.add_task(task, "publish", day)
    return {"status": "accepted"}
