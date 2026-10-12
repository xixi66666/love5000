from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import settings
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

COLLECTION_LOCK_NAME = "skill_finder_collection"


class CollectionLockLease:
    """Holds a dedicated connection that owns a MySQL named lock."""

    def __init__(self, connection: AsyncConnection, engine: Any) -> None:
        self._connection = connection
        self._engine = engine

    async def release(self) -> None:
        try:
            await self._connection.execute(sa.text(f"SELECT RELEASE_LOCK('{COLLECTION_LOCK_NAME}')"))
        finally:
            await self._connection.close()
            await self._engine.dispose()


async def acquire_collection_lock() -> CollectionLockLease | None:
    engine = create_async_engine(settings.database_url, poolclass=sa.pool.NullPool)
    connection = await engine.connect()
    try:
        result = await connection.execute(
            sa.text(f"SELECT GET_LOCK('{COLLECTION_LOCK_NAME}', 0)")
        )
        acquired = result.scalar() == 1
    except Exception:
        await connection.close()
        await engine.dispose()
        raise
    if not acquired:
        await connection.close()
        await engine.dispose()
        return None
    return CollectionLockLease(connection, engine)


async def run_collection(lease: CollectionLockLease | None) -> None:
    """Execute a collection run within a held lock lease, releasing it on exit."""
    from app.collector.github_client import GitHubClient
    from app.collector.service import CollectionService
    from app.collector.trending import TrendingScraper
    from app.repositories.collection_runs import CollectionRunStore
    from app.repositories.repositories import RepositoryStore
    from app.repositories.snapshots import SnapshotStore
    from app.repositories.trending import TrendingStore

    try:
        async with (
            async_session_factory() as session,
            GitHubClient(token=settings.github_token.get_secret_value()) as github_client,
        ):
            service = CollectionService(
                scraper=TrendingScraper(proxy=settings.trending_proxy),
                github_client=github_client,
                repository_store=RepositoryStore(session),
                snapshot_store=SnapshotStore(session),
                trending_store=TrendingStore(session),
                run_store=CollectionRunStore(session),
                session=session,
                business_timezone=settings.business_timezone,
                top_n=settings.trending_top_n,
                ai_keywords=settings.trending_ai_keywords,
                trigger_type="manual",
            )
            result = await service.run()
            logger.info(
                "collection run %s finished with status %s",
                result.run_id,
                result.status,
            )
    finally:
        if lease is not None:
            await lease.release()


def _scheduler_job() -> None:
    import asyncio

    asyncio.run(_scheduled_collection())


async def _scheduled_collection() -> None:
    lease = await acquire_collection_lock()
    if lease is None:
        logger.info("collection skipped: another run holds the lock")
        return
    await run_collection(lease)


def start_scheduler() -> Any:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone=settings.business_timezone)
    if settings.scheduler_enabled:
        scheduler.add_job(
            _scheduler_job,
            "cron",
            id="collection",
            replace_existing=True,
            **(_parse_cron(settings.collection_cron)),
        )
        scheduler.start()
    return scheduler


def _parse_cron(expr: str) -> dict[str, str]:
    minute, hour, day, month, day_of_week = expr.split()
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }
