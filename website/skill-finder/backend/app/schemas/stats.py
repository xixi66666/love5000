from __future__ import annotations

from pydantic import BaseModel


class LanguageStat(BaseModel):
    language: str
    count: int


class StatsResponse(BaseModel):
    total_repositories: int
    positive_growth_today: int
    last_successful_collection_at: str | None = None
    last_run_status: str | None = None
