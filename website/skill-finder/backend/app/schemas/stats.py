"""统计与语言分布的响应模型。

``StatsResponse`` 同时服务首页卡片与刷新轮询：``last_run_id`` 让前端识别“这是不是我
刚触发的那一轮”，``last_run_error`` / ``last_run_warning`` 是服务端拼好的固定提示
（不含异常原文、连接串或凭据）。
"""
from __future__ import annotations

from pydantic import BaseModel


class LanguageStat(BaseModel):
    """一种语言及其仓库数，供前端筛选下拉使用。"""

    language: str
    count: int


class StatsResponse(BaseModel):
    """仪表盘统计。

    字段语义：``total_repositories`` 为可见仓库总数，``positive_growth_today`` 为当日
    增量大于 0 的榜单条目数，``last_run_status`` 为最近一次任务状态；
    ``last_run_error`` 只在 ``FAILED`` 时有值，``last_run_warning`` 只在 ``PARTIAL``
    时有值，未取到最新任务时二者与 ``last_run_id`` 均为 ``None``。
    """

    total_repositories: int
    positive_growth_today: int
    last_successful_collection_at: str | None = None
    last_run_status: str | None = None
    last_run_id: int | None = None
    last_run_error: str | None = None
    last_run_warning: str | None = None
