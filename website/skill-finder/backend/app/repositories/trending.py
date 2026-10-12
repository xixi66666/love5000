from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrendingEntry


@dataclass(frozen=True)
class TrendingEntryValue:
    repository_id: int
    rank_position: int
    stars_gained: int
    stars_total: int


class TrendingStore:
    """Replaces the current Top N snapshot for one trending period."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_period(
        self,
        period: str,
        entries: list[TrendingEntryValue],
        fetched_at: datetime,
    ) -> None:
        await self._session.execute(
            delete(TrendingEntry).where(TrendingEntry.period == period)
        )
        if not entries:
            return
        await self._session.execute(
            insert(TrendingEntry),
            [
                {
                    "repository_id": entry.repository_id,
                    "period": period,
                    "rank_position": entry.rank_position,
                    "stars_gained": entry.stars_gained,
                    "stars_total": entry.stars_total,
                    "fetched_at": fetched_at,
                }
                for entry in entries
            ],
        )
