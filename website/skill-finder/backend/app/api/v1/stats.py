"""首页统计与语言分布端点（``/api/v1`` 前缀）。

``GET /api/v1/stats`` 返回仓库总数、当日正增长条目数以及最近一次采集的状态、编号、
失败原因与部分成功警告；``GET /api/v1/languages`` 返回按仓库数降序的语言分布。
响应模型见 :mod:`app.schemas.stats`；会话由 ``get_db_session`` 打开并保持只读，
失败提示由服务层转换成固定文案，不包含异常原文、连接串或凭据。
"""
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
    """返回仪表盘统计。

    请求：``GET /api/v1/stats``。
    响应：``StatsResponse``，含 ``total_repositories``、``positive_growth_today``，
    以及最近一次采集的 ``last_run_status`` / ``last_run_id`` / ``last_run_error`` /
    ``last_run_warning``；前端的刷新轮询靠 ``last_run_id`` 识别本次任务。

    Args:
        session: ``get_db_session`` 提供的只读会话，由依赖关闭，本函数不 commit。
        service: 统计服务，只做只读聚合查询。
    """
    return await service.get_stats(session)


@router.get("/languages", response_model=list[LanguageStat])
async def get_languages(
    session: AsyncSession = Depends(get_db_session),
    service: StatsService = Depends(get_stats_service),
) -> list[dict]:
    """返回语言分布，供前端筛选下拉使用。

    请求：``GET /api/v1/languages``。
    响应：``[{"language": ..., "count": ...}]``，按仓库数降序、同数按语言名升序；
    未标注语言的仓库不出现。

    Args:
        session: ``get_db_session`` 提供的只读会话。
        service: 统计服务。
    """
    return await service.get_languages(session)
