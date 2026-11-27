"""``/api/v1`` 路由共用的 FastAPI 依赖。

提供三件事：按配置构造无状态服务实例（RepositoryService / StatsService）、
用 ``X-Admin-Key`` 校验管理端请求、以及管理接口的 401 语义。
密钥来自 ``settings.admin_key``（``backend/.env`` 或环境变量）；比较走
:func:`secrets.compare_digest` 以规避时序侧信道，未配置密钥时一律拒绝而不是放行，
且任何分支都不会把期望值写进日志或响应。
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.services.repository_service import RepositoryService
from app.services.stats_service import StatsService

# 管理接口的密钥请求头名称；require_admin_key 依靠参数名 x_admin_key 映射到同名头。
ADMIN_KEY_HEADER = "X-Admin-Key"


def get_repository_service() -> RepositoryService:
    """构造榜单查询服务。

    业务时区取自 ``settings.business_timezone``，用于把“今天”换算成业务日期，
    保证每日 Star 增量与 ``collection_runs`` 的落库口径一致。

    Returns:
        无状态的 RepositoryService；数据库会话由路由层通过 ``get_db_session``
        注入，本函数不持有连接，也不开启事务。
    """
    return RepositoryService(business_timezone=settings.business_timezone)


def get_stats_service() -> StatsService:
    """构造统计服务。

    Returns:
        无状态的 StatsService；所有查询都接收调用方传入的 ``AsyncSession``。
    """
    return StatsService()


def verify_admin_key(value: str | None) -> bool:
    """判断请求头里的管理密钥是否与配置一致。

    Args:
        value: 请求头 ``X-Admin-Key`` 的原始值，可能缺失（``None``）。

    Returns:
        仅当请求头非空、``settings.admin_key`` 已配置且两者完全相同时返回 ``True``；
        密钥未配置属于“不可用”，同样返回 ``False``，避免空字符串意外通过。
    """
    if not value:
        return False
    expected = settings.admin_key.get_secret_value()
    if not expected:
        return False
    return secrets.compare_digest(value, expected)


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """FastAPI 依赖：管理端点必须携带正确的 ``X-Admin-Key``。

    直接返回 ``None``，由路由以 ``dependencies=[Depends(require_admin_key)]`` 挂载，
    因此这个依赖只承担“不通过就中断请求”的职责。

    Args:
        x_admin_key: FastAPI 从请求头注入，缺省为 ``None``。

    Raises:
        HTTPException: 密钥缺失或不匹配时返回 401，detail 固定为 ``Invalid admin key``，
            不回显期望值，便于前端区分“缺少凭据”和业务失败。
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )
