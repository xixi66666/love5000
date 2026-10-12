from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.services.repository_service import RepositoryService
from app.services.stats_service import StatsService

ADMIN_KEY_HEADER = "X-Admin-Key"


def get_repository_service() -> RepositoryService:
    return RepositoryService(business_timezone=settings.business_timezone)


def get_stats_service() -> StatsService:
    return StatsService()


def verify_admin_key(value: str | None) -> bool:
    if not value:
        return False
    expected = settings.admin_key.get_secret_value()
    if not expected:
        return False
    return secrets.compare_digest(value, expected)


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    if not verify_admin_key(x_admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )
