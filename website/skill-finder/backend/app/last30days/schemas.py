"""近 30 天研究的请求与响应模型。

`StatusType` 是前端状态机的唯一取值来源：`working` 有结果且来源正常，`partial`
有结果但部分来源降级，`no-results` 正常完成却没抓到内容，`error` 引擎或来源失败，
`skipped` 模块被禁用，`unconfigured` 找不到 skill 或 Python 运行时。

字段刻意宽松（`Any`、空字符串、默认集合）：不同版本的引擎输出差异较大，这里只做
结构约束，缺失字段由服务层决定如何降级，不在模型层报错。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# 前端状态机取值：working / partial / no-results / error / skipped / unconfigured。
StatusType = Literal[
    "working",
    "no-results",
    "partial",
    "error",
    "skipped",
    "unconfigured",
]

# 榜单方向：agent 与 skill 各自维护一份缓存榜单。
DirectionType = Literal["agent", "skill"]


class Last30DaysRequest(BaseModel):
    """任意主题研究的请求体，保留给调试接口使用。

    `query` 去空白后不得为空，`limit` 限制在 1 到 100 之间。
    """
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        """去掉首尾空白；结果为空时拒绝，避免把空主题交给多源抓取。"""
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("研究主题不能为空")
        return clean_value


class Last30DaysCluster(BaseModel):
    """引擎把多条讨论聚成的话题簇，用于页面上的分组浏览。"""
    title: str
    summary: str = ""
    sources: list[str] = Field(default_factory=list)
    engagement_total: int | float = 0


class Last30DaysItem(BaseModel):
    """单条研究结果：标题、来源、链接、互动数据与可能的聚类归属。

    字段大多有默认值，用来兼容不同版本引擎缺字段的输出，而不是在解析阶段报错。
    """
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
    """任意主题研究的返回体，含逐来源状态。

    `status` 由服务层按“有无条目、有无降级来源”推导；`source_status` 原样保留引擎
    给出的每个来源状态，便于前端展示哪一路失败。
    """
    status: StatusType
    query: str = ""
    items: list[Last30DaysItem] = Field(default_factory=list)
    clusters: list[Last30DaysCluster] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_status: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    message: str | None = None


class Last30DaysStatusResponse(BaseModel):
    """诊断接口的返回体：运行时是否可用以及当前可用的来源。"""
    status: StatusType
    sources: list[str] = Field(default_factory=list)
    message: str | None = None


class Last30DaysRefreshRequest(BaseModel):
    """刷新请求：只允许 agent 与 skill 两个固定方向。"""
    direction: DirectionType


class Last30DaysRankingResponse(BaseModel):
    """缓存榜单的返回体；从未刷新时 `fetched_at` 是空串，而不是当前时间。"""
    direction: DirectionType
    status: StatusType
    items: list[Last30DaysItem] = Field(default_factory=list)
    clusters: list[Last30DaysCluster] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_status: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = ""
    message: str | None = None
