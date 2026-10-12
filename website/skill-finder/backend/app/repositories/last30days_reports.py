from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Last30DaysReport


class Last30DaysReportStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, direction: str) -> Last30DaysReport | None:
        result = await self._session.execute(
            select(Last30DaysReport).where(Last30DaysReport.direction == direction)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        direction: str,
        status: str,
        payload: dict[str, Any],
        message: str | None,
        fetched_at: datetime,
    ) -> None:
        report = await self.get(direction)
        if report is None:
            report = Last30DaysReport(
                direction=direction,
                status=status,
                payload=payload,
                message=message,
                fetched_at=fetched_at,
            )
            self._session.add(report)
        else:
            report.status = status
            report.payload = payload
            report.message = message
            report.fetched_at = fetched_at
        await self._session.flush()
