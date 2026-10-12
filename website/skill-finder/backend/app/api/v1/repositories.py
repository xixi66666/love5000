from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_repository_service
from app.db.session import get_db_session
from app.schemas.common import PageParams
from app.schemas.repository import RepositoryDetail, RepositoryListResponse
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])

CATEGORIES = ("AGENT", "SKILL", "MCP", "PLUGIN")
SORTS = ("daily_stars", "weekly_stars", "monthly_stars", "total_stars")


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    session: AsyncSession = Depends(get_db_session),
    service: RepositoryService = Depends(get_repository_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(
        default="daily_stars",
        pattern="^(daily_stars|weekly_stars|monthly_stars|total_stars)$",
    ),
    category: str | None = Query(default=None, pattern="^(AGENT|SKILL|MCP|PLUGIN)$"),
    language: str | None = Query(default=None, max_length=100),
    min_stars: int | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=200),
) -> dict:
    page_params = PageParams(page=page, page_size=page_size)
    return await service.list_repositories(
        session,
        page_params,
        sort=sort,
        category=category,
        language=language,
        min_stars=min_stars,
        q=q,
    )


@router.get("/{owner}/{name}", response_model=RepositoryDetail)
async def get_repository_detail(
    owner: str,
    name: str,
    session: AsyncSession = Depends(get_db_session),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryDetail:
    return await service.get_detail(session, owner, name)
