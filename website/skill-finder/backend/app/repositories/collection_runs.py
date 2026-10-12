from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionRun


class CollectionRunStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, trigger_type: str) -> CollectionRun:
        run = CollectionRun(
            status="RUNNING",
            trigger_type=trigger_type,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def finish(
        self,
        run: CollectionRun,
        *,
        status: str,
        query_count: int,
        discovered_count: int,
        updated_count: int,
        failed_count: int,
        rate_limit_remaining: int | None,
        rate_limit_reset_at: datetime | None,
        error_summary: str | None,
    ) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.query_count = query_count
        run.discovered_count = discovered_count
        run.updated_count = updated_count
        run.failed_count = failed_count
        run.rate_limit_remaining = rate_limit_remaining
        run.rate_limit_reset_at = rate_limit_reset_at
        run.error_summary = error_summary
        await self._session.flush()

    async def latest(self) -> CollectionRun | None:
        result = await self._session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
