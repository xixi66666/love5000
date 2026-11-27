"""近 30 天多源研究端点（挂在 ``/api/v1`` 前缀下，路由自身不带 prefix）。

- ``GET /last30days/status``：诊断本机 skill 目录、Python 解释器等前置条件；
- ``POST /last30days``：即时抓取一次多源内容；
- ``GET /last30days/rankings``：读取已落库的榜单；
- ``POST /last30days/rankings/refresh``：重新抓取并覆盖落库。

会话由 ``get_db_session`` 打开、请求结束时关闭；本模块不自行 commit，
``refresh_ranking`` 内部完成写入与提交。上游 skill 缺失或超时时返回带错误的
诊断结果，而不是让整个页面 500。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.last30days.schemas import (
    DirectionType,
    Last30DaysRankingResponse,
    Last30DaysRefreshRequest,
    Last30DaysRequest,
    Last30DaysResponse,
    Last30DaysStatusResponse,
)
from app.last30days.service import (
    diagnose_last30days,
    fetch_last30days,
    get_ranking,
    refresh_ranking,
)

router = APIRouter()


@router.get("/last30days/status", response_model=Last30DaysStatusResponse)
async def last30days_status_endpoint() -> Last30DaysStatusResponse:
    """返回近 30 天研究的环境诊断。

    请求：``GET /api/v1/last30days/status``。
    响应：``Last30DaysStatusResponse``，说明 skill 目录、解释器与记忆目录是否就绪，
    不可用时给出原因，供前端禁用“刷新”按钮而不是直接报错。
    """
    return Last30DaysStatusResponse(**await diagnose_last30days())


@router.post("/last30days", response_model=Last30DaysResponse)
async def last30days_endpoint(request: Last30DaysRequest) -> Last30DaysResponse:
    """即时执行一次近 30 天多源抓取，不落库。

    请求：``POST /api/v1/last30days``，体为 ``Last30DaysRequest``（查询词与条数）。
    响应：``Last30DaysResponse``；单个来源失败只影响对应条目，
    整体结果仍会返回（可能带错误说明），不会因为一个来源超时就让请求 500。
    """
    result = await fetch_last30days(query=request.query, limit=request.limit)
    return Last30DaysResponse(**result)


@router.get("/last30days/rankings", response_model=Last30DaysRankingResponse)
async def last30days_ranking_endpoint(
    direction: DirectionType = Query(default="agent"),
    session: AsyncSession = Depends(get_db_session),
) -> Last30DaysRankingResponse:
    """读取已落库的近 30 天榜单。

    请求：``GET /api/v1/last30days/rankings?direction=agent|skill``。
    响应：``Last30DaysRankingResponse``；从未抓取过时返回空榜单而非 404，
    页面据此显示“尚未生成”。

    Args:
        direction: 研究方向，``agent`` 或 ``skill``，默认 ``agent``。
        session: ``get_db_session`` 提供的只读会话，由依赖关闭。
    """
    return Last30DaysRankingResponse(**await get_ranking(session, direction))


@router.post("/last30days/rankings/refresh", response_model=Last30DaysRankingResponse)
async def last30days_refresh_endpoint(
    request: Last30DaysRefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Last30DaysRankingResponse:
    """重新抓取指定方向并覆盖落库的榜单。

    请求：``POST /api/v1/last30days/rankings/refresh``，体含 ``direction``。
    响应：``Last30DaysRankingResponse``（本次抓取后的最新榜单）。

    写入与提交都在 ``refresh_ranking`` 内部完成，本路由不额外开启事务；
    抓取失败时保留上一次结果并带回错误说明，不会覆盖成空榜单。

    Args:
        request: 含 ``direction`` 的请求体。
        session: ``get_db_session`` 提供的会话，提交后仍在请求生命周期内由依赖关闭。
    """
    return Last30DaysRankingResponse(**await refresh_ranking(session, request.direction))
