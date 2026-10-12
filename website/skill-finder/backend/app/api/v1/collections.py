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

REFRESH_COOLDOWN = "REFRESH_COOLDOWN"
COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"


@router.post("/collections/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_collection(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    latest = await CollectionRunStore(session).latest()
    cooldown = timedelta(minutes=settings.refresh_cooldown_minutes)
    if latest is not None and latest.started_at is not None:
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
