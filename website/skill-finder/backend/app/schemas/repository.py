from __future__ import annotations

from pydantic import BaseModel


class RepositoryListItem(BaseModel):
    id: int
    owner: str
    name: str
    description: str | None = None
    html_url: str
    language: str | None = None
    topics: list[str] = []
    categories: list[str] = []
    stars_count: int
    daily_stars: int | None = None
    weekly_stars: int | None = None
    monthly_stars: int | None = None
    last_synced_at: str | None = None
    trend: list[dict] = []


class RepositoryListResponse(BaseModel):
    items: list[RepositoryListItem]
    page: int
    page_size: int
    total: int
    last_successful_collection_at: str | None = None


class TrendPoint(BaseModel):
    snapshot_date: str
    stars_count: int


class RepositoryIntroduction(BaseModel):
    introduction: str
    highlights: list[str] = []
    requirements: list[str] = []
    usage: str = ""
    audience: str = ""
    domains: list[str] = []


class RepositoryDetail(BaseModel):
    id: int
    owner: str
    name: str
    description: str | None = None
    introduction: RepositoryIntroduction | None = None
    html_url: str
    homepage: str | None = None
    language: str | None = None
    topics: list[str] = []
    categories: list[str] = []
    matched_rules: list[str] = []
    stars_count: int
    forks_count: int
    open_issues_count: int
    daily_stars: int | None = None
    weekly_stars: int | None = None
    monthly_stars: int | None = None
    last_synced_at: str | None = None
    github_created_at: str | None = None
    trend: list[TrendPoint] = []
