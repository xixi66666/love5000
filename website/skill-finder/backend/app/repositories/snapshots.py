from __future__ import annotations

from datetime import date

from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StarSnapshot


class SnapshotStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_daily(
        self, repository_id: int, snapshot_date: date, stars_count: int
    ) -> None:
        stmt = insert(StarSnapshot).values(
            repository_id=repository_id,
            snapshot_date=snapshot_date,
            stars_count=stars_count,
        )
        stmt = stmt.on_duplicate_key_update(stars_count=stmt.inserted["stars_count"])
        await self._session.execute(stmt)
