"""手动刷新榜单的公开端点。

``POST /api/v1/collections/refresh``：先做冷却判断，再抢 MySQL 命名锁，通过后把采集
丢进 BackgroundTasks 并立即回 202。

冷却只针对非 ``FAILED`` 的上一次任务——失败允许立刻重试，避免一次网络抖动就把用户
锁在 30 分钟之外；成功或部分成功仍保留 30 分钟冷却，并发由命名锁兜底。
会话由 ``get_db_session`` 依赖打开并在请求结束时关闭，本模块只读
``collection_runs``，不提交任何写事务；采集本身在后台用独立会话完成。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.scheduler import acquire_collection_lock, run_collection
from app.db.session import get_db_session
from app.repositories.collection_runs import CollectionRunStore

router = APIRouter(tags=["collections"])

# 稳定错误码：前端据此区分“等一会再试”（冷却）与“已经有人在跑”（并发冲突）。
REFRESH_COOLDOWN = "REFRESH_COOLDOWN"
COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"


@router.post("/collections/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_collection(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """请求刷新榜单（前端“刷新”按钮）。

    请求：``POST /api/v1/collections/refresh``，无请求体。
    响应：202 ``{"status": "accepted"}``。

    判定顺序：最近一次 ``collection_runs`` 若不是 ``FAILED`` 且距今不足
    ``settings.refresh_cooldown_minutes`` 分钟，回 429 并给出剩余分钟数；
    否则尝试抢命名锁，抢不到回 409；两者都通过才排队后台任务。
    ``started_at`` 可能是无时区的 MySQL DATETIME，比较前先补成 UTC。

    Args:
        background_tasks: FastAPI 注入，承载后台采集协程。
        session: ``get_db_session`` 提供的只读会话，由依赖负责关闭；本函数不 commit。

    Raises:
        HTTPException: 429 冷却中（detail 含 ``REFRESH_COOLDOWN``），
            或 409 已有采集在运行（detail 含 ``COLLECTION_ALREADY_RUNNING``）。
    """
    latest = await CollectionRunStore(session).latest()
    cooldown = timedelta(minutes=settings.refresh_cooldown_minutes)
    if latest is not None and latest.status != "FAILED" and latest.started_at is not None:
        started_at = latest.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - started_at
        if elapsed < cooldown:
            remaining_minutes = max(1, ceil((cooldown - elapsed).total_seconds() / 60))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": REFRESH_COOLDOWN,
                    "message": f"刚触发过采集，请约 {remaining_minutes} 分钟后再试。",
                },
            )
    lease = await acquire_collection_lock()
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": COLLECTION_ALREADY_RUNNING,
                "message": "已有采集任务在进行中，请稍后再试。",
            },
        )
    background_tasks.add_task(run_collection, lease)
    return {"status": "accepted"}
