from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

StatusType = Literal[
    "working",
    "no-results",
    "partial",
    "error",
    "skipped",
    "unconfigured",
]

DirectionType = Literal["agent", "skill"]


class Last30DaysRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("研究主题不能为空")
        return clean_value


class Last30DaysCluster(BaseModel):
    title: str
    summary: str = ""
    sources: list[str] = Field(default_factory=list)
    engagement_total: int | float = 0


class Last30DaysItem(BaseModel):
    candidate_id: str
    title: str
    source: str
    url: str
    published_at: str = ""
    summary: str = ""
    engagement: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float | None = None
    cluster: int | None = None


class Last30DaysResponse(BaseModel):
    status: StatusType
    query: str = ""
    items: list[Last30DaysItem] = Field(default_factory=list)
    clusters: list[Last30DaysCluster] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_status: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    message: str | None = None


class Last30DaysStatusResponse(BaseModel):
    status: StatusType
    sources: list[str] = Field(default_factory=list)
    message: str | None = None


class Last30DaysRefreshRequest(BaseModel):
    direction: DirectionType


class Last30DaysRankingResponse(BaseModel):
    direction: DirectionType
    status: StatusType
    items: list[Last30DaysItem] = Field(default_factory=list)
    clusters: list[Last30DaysCluster] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_status: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = ""
    message: str | None = None
