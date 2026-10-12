from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.last30days.schemas import (
    DirectionType,
    Last30DaysRankingResponse,
    Last30DaysRefreshRequest,
    Last30DaysRequest,
    Last30DaysResponse,
    Last30DaysStatusResponse,
)
from app.last30days.service import (
    diagnose_last30days,
    fetch_last30days,
    get_ranking,
    refresh_ranking,
)

router = APIRouter()


@router.get("/last30days/status", response_model=Last30DaysStatusResponse)
async def last30days_status_endpoint() -> Last30DaysStatusResponse:
    return Last30DaysStatusResponse(**await diagnose_last30days())


@router.post("/last30days", response_model=Last30DaysResponse)
async def last30days_endpoint(request: Last30DaysRequest) -> Last30DaysResponse:
    result = await fetch_last30days(query=request.query, limit=request.limit)
    return Last30DaysResponse(**result)


@router.get("/last30days/rankings", response_model=Last30DaysRankingResponse)
async def last30days_ranking_endpoint(
    direction: DirectionType = Query(default="agent"),
    session: AsyncSession = Depends(get_db_session),
) -> Last30DaysRankingResponse:
    return Last30DaysRankingResponse(**await get_ranking(session, direction))


@router.post("/last30days/rankings/refresh", response_model=Last30DaysRankingResponse)
async def last30days_refresh_endpoint(
    request: Last30DaysRefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Last30DaysRankingResponse:
    return Last30DaysRankingResponse(**await refresh_ranking(session, request.direction))
