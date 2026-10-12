from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_stats_service
from app.db.session import get_db_session
from app.schemas.stats import LanguageStat, StatsResponse
from app.services.stats_service import StatsService

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
    service: StatsService = Depends(get_stats_service),
) -> dict:
    return await service.get_stats(session)


@router.get("/languages", response_model=list[LanguageStat])
async def get_languages(
    session: AsyncSession = Depends(get_db_session),
    service: StatsService = Depends(get_stats_service),
) -> list[dict]:
    return await service.get_languages(session)
