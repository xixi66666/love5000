"""榜单与详情的响应模型。

``RepositoryListItem`` 只带列表需要的摘要字段（三个周期增量 + 总 Star），
``RepositoryDetail`` 额外带中文简介、fork/issue 与近 30 天曲线；
``RepositoryIntroduction`` 对应 ``repositories.introduction`` 里保存的 JSON 结构，
解析失败时由服务层退化成只有 ``introduction`` 的纯文本对象。
"""
from __future__ import annotations

from pydantic import BaseModel


class RepositoryListItem(BaseModel):
    """榜单行。

    ``daily_stars`` / ``weekly_stars`` / ``monthly_stars`` 为 ``None`` 表示该仓库不在对应
    周期的榜单里（模型或候选不足）；``trend`` 在列表里恒为空，曲线只在详情返回。
    """

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
    """分页榜单响应。

    ``total`` 是过滤后的总条数（用于前端分页器）；``last_successful_collection_at``
    取最近一次 ``SUCCESS``/``PARTIAL`` 任务的结束时间，从未成功过时为 ``None``。
    """

    items: list[RepositoryListItem]
    page: int
    page_size: int
    total: int
    last_successful_collection_at: str | None = None


class TrendPoint(BaseModel):
    """Star 曲线上的一个点。

    ``snapshot_date`` 是业务时区的日期字符串，``stars_count`` 是当日总 Star。
    """

    snapshot_date: str
    stars_count: int


class RepositoryIntroduction(BaseModel):
    """结构化中文简介。

    与 ``repositories.introduction`` 中保存的 JSON 一一对应；``introduction`` 之外
    各字段缺失时用空列表/空串兜底，前端无需做空值判断。
    """

    introduction: str
    highlights: list[str] = []
    requirements: list[str] = []
    usage: str = ""
    audience: str = ""
    domains: list[str] = []


class RepositoryDetail(BaseModel):
    """仓库详情。

    ``introduction`` 为 ``None`` 表示还没生成（页面显示“暂未生成中文介绍”，不会现场
    调用模型）；三个周期增量缺失时服务层会用 ``star_snapshots`` 回退计算；
    ``trend`` 最多 30 个点，按日期升序。
    """

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
