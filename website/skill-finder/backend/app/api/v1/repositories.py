"""仓库榜单与详情端点（``/api/v1/repositories``）。

列表接口把分类、语言、最低 Star、关键词与排序组合起来，按业务时区换算的
当日/本周/本月增量做稳定分页（``None`` 值排在最后，再用总 Star 与 id 兜底）；
详情接口返回中文介绍、三个周期的增量与近 30 天 Star 曲线。
详情不存在时服务层抛 ``ApiError(REPOSITORY_NOT_FOUND, ..., 404)``，由统一错误处理器
转成错误体，因此这里没有 try/except；会话由 ``get_db_session`` 提供，本模块不提交事务。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_repository_service
from app.db.session import get_db_session
from app.schemas.common import PageParams
from app.schemas.repository import RepositoryDetail, RepositoryListResponse
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])

# 分类取值与 collector.classifier 的输出一致；排序键覆盖三个榜单增量与总 Star。
# 真正的入参校验在下面 Query 的 pattern 上，这两个元组用于表达允许集合、便于阅读。
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
    """分页返回榜单。

    请求：``GET /api/v1/repositories?page=1&page_size=20&sort=daily_stars
    &category=AGENT&language=Python&min_stars=0&q=agent``。
    响应：``RepositoryListResponse``，含 ``items`` / ``page`` / ``page_size`` / ``total``
    与 ``last_successful_collection_at``（没有成功记录时为 ``null``）。

    Args:
        session: ``get_db_session`` 提供的只读会话，由依赖关闭，本函数不 commit。
        service: 榜单服务，负责三个周期的关联子查询与排序。
        page: 页码，从 1 开始。
        page_size: 每页条数，1-100，默认 20。
        sort: 排序键，非法值由 Query 的 pattern 拦截为 422。
        category: 分类过滤，命中 ``repositories.categories`` JSON 文本中的分类名。
        language: 语言精确匹配，最长 100 字符。
        min_stars: 总 Star 下限，含边界。
        q: 关键词，对 owner/name/description 做 LIKE 匹配，最长 200 字符。
    """
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
    """返回单个仓库的详情。

    请求：``GET /api/v1/repositories/{owner}/{name}``。
    响应：``RepositoryDetail``；介绍缺失时 ``introduction`` 为 ``null``（前端显示
    “暂未生成中文介绍”），三个周期增量缺失时回退到 ``star_snapshots`` 计算。

    Args:
        owner: 仓库所有者，路径参数，按库中存值精确匹配。
        name: 仓库名，路径参数，按库中存值精确匹配。
        session: ``get_db_session`` 提供的只读会话。
        service: 详情服务。

    Raises:
        ApiError: 仓库不存在或已标记 ``available=false`` 时由服务层抛出（404），
            再经 ``api_error_handler`` 转成统一错误体。
    """
    return await service.get_detail(session, owner, name)
