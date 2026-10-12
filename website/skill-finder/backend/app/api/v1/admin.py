from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import require_admin_key
from app.core.scheduler import acquire_collection_lock, run_collection

router = APIRouter(prefix="/admin", tags=["admin"])

COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"


@router.post("/collections", status_code=status.HTTP_202_ACCEPTED)
async def trigger_collection(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_key),
) -> dict[str, str]:
    lease = await acquire_collection_lock()
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": COLLECTION_ALREADY_RUNNING,
                "message": "A collection run is already in progress",
            },
        )
    background_tasks.add_task(run_collection, lease)
    return {"status": "accepted"}


@router.post("/introductions", status_code=status.HTTP_202_ACCEPTED)
async def trigger_introduction_backfill(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_key),
    category: str | None = Query(default=None, pattern="^(AGENT|SKILL|MCP|PLUGIN)$"),
    limit: int = Query(default=5, ge=1, le=100),
    order: str | None = Query(default=None, pattern="^daily$"),
) -> dict[str, str]:
    background_tasks.add_task(
        run_introduction_backfill, category=category, limit=limit, order=order
    )
    return {"status": "accepted"}


async def run_introduction_backfill(
    *, category: str | None, limit: int, order: str | None
) -> None:
    from app.services.introduction_service import run_introduction_backfill as backfill

    await backfill(category=category, limit=limit, order=order)
