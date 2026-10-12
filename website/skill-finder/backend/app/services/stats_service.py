from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionRun, Repository, TrendingEntry


class StatsService:
    async def get_stats(self, session: AsyncSession) -> dict:
        total = await session.scalar(
            select(func.count(Repository.id)).where(Repository.available.is_(True))
        )

        positive_growth = await session.scalar(
            select(func.count(TrendingEntry.id)).where(
                TrendingEntry.period == "daily",
                TrendingEntry.stars_gained > 0,
            )
        )

        success_row = await session.execute(
            select(CollectionRun)
            .where(CollectionRun.status.in_(("SUCCESS", "PARTIAL")))
            .order_by(CollectionRun.finished_at.desc())
            .limit(1)
        )
        success = success_row.scalar_one_or_none()

        latest_run_row = await session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        latest_run = latest_run_row.scalar_one_or_none()

        return {
            "total_repositories": total,
            "positive_growth_today": positive_growth,
            "last_successful_collection_at": _iso(success.finished_at if success else None),
            "last_run_status": latest_run.status if latest_run else None,
        }

    async def get_languages(self, session: AsyncSession) -> list[dict]:
        rows = await session.execute(
            select(Repository.language, func.count(Repository.id).label("count"))
            .where(
                Repository.available.is_(True),
                Repository.language.isnot(None),
            )
            .group_by(Repository.language)
            .order_by(func.count(Repository.id).desc(), Repository.language.asc())
        )
        return [{"language": language, "count": count} for language, count in rows.all()]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
