"""分页参数与统一错误响应。

``PageParams`` 在路由层把 Query 参数收拢成一个对象再传给服务，边界值（``page >= 1``、
``1 <= page_size <= 100``）在这里声明一次；``ErrorResponse`` 是 ``app.api.errors`` 里
三个异常处理器共同使用的响应体，前端按 ``code`` 分支、按 ``request_id`` 对日志。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PageParams(BaseModel):
    """分页参数。

    ``page`` 从 1 开始；``page_size`` 上限 100，防止单次查询把整张表拉进内存。
    越界值由 Pydantic 校验抛出，FastAPI 会转成 422。
    """

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ErrorResponse(BaseModel):
    """统一错误体。

    ``code`` 是稳定错误码（如 ``REPOSITORY_NOT_FOUND``），``message`` 是可展示的说明，
    ``request_id`` 取自请求头 ``x-request-id``，缺失时为空串。三者都不应包含
    数据库连接串、Token 或内部路径。
    """

    code: str
    message: str
    request_id: str
