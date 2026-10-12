from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import REPOSITORY_NOT_FOUND, ApiError
from app.db.models import CollectionRun, Repository, StarSnapshot, TrendingEntry
from app.schemas.common import PageParams
from app.schemas.repository import (
    RepositoryDetail,
    RepositoryIntroduction,
    RepositoryListItem,
)


class RepositoryService:
    def __init__(self, business_timezone: str = "Asia/Shanghai") -> None:
        self._timezone = ZoneInfo(business_timezone)

    async def list_repositories(
        self,
        session: AsyncSession,
        page_params: PageParams,
        *,
        sort: str,
        category: str | None,
        language: str | None,
        min_stars: int | None,
        q: str | None,
    ) -> dict:
        daily = self._trending_subquery("daily")
        weekly = self._trending_subquery("weekly")
        monthly = self._trending_subquery("monthly")

        daily_stars = daily.c.daily_stars
        weekly_stars = weekly.c.weekly_stars
        monthly_stars = monthly.c.monthly_stars

        query = (
            select(Repository, daily_stars, weekly_stars, monthly_stars)
            .outerjoin(daily, Repository.id == daily.c.repository_id)
            .outerjoin(weekly, Repository.id == weekly.c.repository_id)
            .outerjoin(monthly, Repository.id == monthly.c.repository_id)
            .where(Repository.available.is_(True))
        )

        if category:
            query = query.where(
                cast(Repository.categories, Text).like(f'%"{category}"%')
            )
        if language:
            query = query.where(Repository.language == language)
        if min_stars is not None:
            query = query.where(Repository.stars_count >= min_stars)
        if q:
            pattern = f"%{q}%"
            query = query.where(
                Repository.owner.like(pattern)
                | Repository.name.like(pattern)
                | Repository.description.like(pattern)
            )

        if sort == "total_stars":
            sort_col = Repository.stars_count
        elif sort == "monthly_stars":
            sort_col = monthly_stars
        elif sort == "weekly_stars":
            sort_col = weekly_stars
        else:
            sort_col = daily_stars

        query = query.order_by(
            sort_col.is_(None),
            sort_col.desc(),
            Repository.stars_count.desc(),
            Repository.id.desc(),
        )

        total = await session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await session.execute(
            query.offset((page_params.page - 1) * page_params.page_size).limit(
                page_params.page_size
            )
        )

        items = [
            self._to_list_item(row, daily, weekly, monthly)
            for row, daily, weekly, monthly in rows.all()
        ]
        last_success = await self._last_successful_collection(session)
        return {
            "items": items,
            "page": page_params.page,
            "page_size": page_params.page_size,
            "total": total,
            "last_successful_collection_at": last_success,
        }

    async def get_detail(
        self, session: AsyncSession, owner: str, name: str
    ) -> RepositoryDetail:
        result = await session.execute(
            select(Repository).where(
                Repository.owner == owner,
                Repository.name == name,
                Repository.available.is_(True),
            )
        )
        repository = result.scalar_one_or_none()
        if repository is None:
            raise ApiError(REPOSITORY_NOT_FOUND, "Repository not found", 404)

        today = datetime.now(self._timezone).date()
        trending = await self._trending_growth(session, repository.id)
        daily = trending.get("daily")
        if daily is None:
            daily = await self._growth_between(session, repository.id, today, 1)
        weekly = trending.get("weekly")
        if weekly is None:
            weekly = await self._growth_between(session, repository.id, today, 7)
        monthly = trending.get("monthly")
        if monthly is None:
            monthly = await self._growth_between(session, repository.id, today, 30)

        trend_rows = await session.execute(
            select(StarSnapshot)
            .where(StarSnapshot.repository_id == repository.id)
            .order_by(StarSnapshot.snapshot_date.desc())
            .limit(30)
        )
        trend = [
            {
                "snapshot_date": snap.snapshot_date.isoformat(),
                "stars_count": snap.stars_count,
            }
            for snap in reversed(trend_rows.scalars().all())
        ]

        return RepositoryDetail(
            id=repository.id,
            owner=repository.owner,
            name=repository.name,
            description=repository.description,
            introduction=_parse_introduction(repository.introduction),
            html_url=repository.html_url,
            homepage=repository.homepage,
            language=repository.language,
            topics=list(repository.topics or []),
            categories=list(repository.categories or []),
            matched_rules=list(repository.matched_rules or []),
            stars_count=repository.stars_count,
            forks_count=repository.forks_count,
            open_issues_count=repository.open_issues_count,
            daily_stars=daily,
            weekly_stars=weekly,
            monthly_stars=monthly,
            last_synced_at=_iso(repository.last_synced_at),
            github_created_at=_iso(repository.github_created_at),
            trend=trend,
        )

    def _trending_subquery(self, period: str):
        return (
            select(
                TrendingEntry.repository_id.label("repository_id"),
                TrendingEntry.stars_gained.label(f"{period}_stars"),
            )
            .where(TrendingEntry.period == period)
            .subquery()
        )

    async def _trending_growth(
        self, session: AsyncSession, repository_id: int
    ) -> dict[str, int | None]:
        rows = await session.execute(
            select(TrendingEntry).where(TrendingEntry.repository_id == repository_id)
        )
        return {
            entry.period: entry.stars_gained
            for entry in rows.scalars().all()
        }

    def _to_list_item(
        self,
        row,
        daily: int | None,
        weekly: int | None,
        monthly: int | None,
    ) -> RepositoryListItem:
        return RepositoryListItem(
            id=row.id,
            owner=row.owner,
            name=row.name,
            description=row.description,
            html_url=row.html_url,
            language=row.language,
            topics=list(row.topics or []),
            categories=list(row.categories or []),
            stars_count=row.stars_count,
            daily_stars=daily,
            weekly_stars=weekly,
            monthly_stars=monthly,
            last_synced_at=_iso(row.last_synced_at),
            trend=[],
        )

    async def _growth_between(
        self, session: AsyncSession, repository_id: int, target: datetime.date, days: int
    ) -> int | None:
        cutoff = target - timedelta(days=days)
        base_row = await session.execute(
            select(StarSnapshot)
            .where(
                StarSnapshot.repository_id == repository_id,
                StarSnapshot.snapshot_date <= cutoff,
            )
            .order_by(StarSnapshot.snapshot_date.desc())
            .limit(1)
        )
        base = base_row.scalar_one_or_none()
        latest_row = await session.execute(
            select(StarSnapshot)
            .where(
                StarSnapshot.repository_id == repository_id,
                StarSnapshot.snapshot_date <= target,
            )
            .order_by(StarSnapshot.snapshot_date.desc())
            .limit(1)
        )
        latest = latest_row.scalar_one_or_none()
        if latest is None or base is None:
            return None
        return latest.stars_count - base.stars_count

    async def _last_successful_collection(self, session: AsyncSession) -> str | None:
        row = await session.execute(
            select(CollectionRun)
            .where(CollectionRun.status.in_(("SUCCESS", "PARTIAL")))
            .order_by(CollectionRun.started_at.desc())
            .limit(1)
        )
        run = row.scalar_one_or_none()
        return _iso(run.finished_at if run else None)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_introduction(raw: str | None) -> RepositoryIntroduction | None:
    """Parse the stored JSON introduction; fall back to a plain-text intro."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            intro = str(data.get("introduction", "")).strip()
            if intro:
                return RepositoryIntroduction(
                    introduction=intro,
                    highlights=[
                        str(h).strip()
                        for h in data.get("highlights", [])
                        if isinstance(h, str) and h.strip()
                    ],
                    requirements=[
                        str(r).strip()
                        for r in data.get("requirements", [])
                        if isinstance(r, str) and r.strip()
                    ],
                    usage=str(data.get("usage", "")).strip(),
                    audience=str(data.get("audience", "")).strip(),
                    domains=[
                        str(d).strip()
                        for d in data.get("domains", [])
                        if isinstance(d, str) and d.strip()
                    ],
                )
    except json.JSONDecodeError:
        pass
    return RepositoryIntroduction(introduction=raw.strip())
