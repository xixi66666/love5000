"""统一错误响应与异常处理器。

对外错误体固定为 ``{"code", "message", "request_id"}``（见
:class:`app.schemas.common.ErrorResponse`），``request_id`` 取自请求头
``x-request-id``，缺失时为空串。三类处理器分工：

- :class:`ApiError`：业务层显式抛出的领域错误，保留 ``code`` 与 ``message``；
- ``StarletteHTTPException``：FastAPI/Starlette 自身产生的 4xx/5xx；
- 其他未捕获异常：统一折叠为 500 与固定文案，绝不把异常栈、SQL、连接串或
  GitHub Token 回给浏览器。
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorResponse

# 前端依据这些稳定错误码区分“详情不存在”“采集已在运行”和兜底失败，不要随意改名。
REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"
INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiError(Exception):
    """带业务错误码与 HTTP 状态码的领域异常。

    由服务层抛出（例如仓库详情不存在），再由 :func:`api_error_handler` 转成统一错误体，
    因此 ``services`` 与 ``repositories`` 不需要 import FastAPI 的异常类型。

    Attributes:
        code: 稳定错误码，供前端分支判断。
        message: 可展示给调用方的说明，不得包含凭据或内部路径。
        status_code: 期望返回的 HTTP 状态码。
    """

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """把 Starlette/FastAPI 的 HTTPException 转成统一错误体。

    路由内用 ``detail={"code": ..., "message": ...}`` 抛出时沿用其中的 code/message；
    其余情况把 detail 文本当作 message，code 记为 ``INTERNAL_ERROR``。
    异常发生在请求处理阶段，这里只做响应转换，不提交也不回滚任何事务。

    Args:
        request: 当前请求，用于读取 ``x-request-id``。
        exc: Starlette 抛出的 HTTPException。

    Returns:
        状态码与 ``exc.status_code`` 一致、响应体为错误结构的 JSONResponse。
    """
    detail = exc.detail
    code = detail.get("code") if isinstance(detail, dict) else INTERNAL_ERROR
    message = detail.get("message") if isinstance(detail, dict) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=code or INTERNAL_ERROR,
            message=message,
            request_id=request.headers.get("x-request-id", ""),
        ).model_dump(),
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """把领域异常 :class:`ApiError` 转成统一错误体。

    Returns:
        状态码取 ``exc.status_code``，``code`` 与 ``message`` 原样透出，
        因而服务层可以自定义 404/409 等语义而不必依赖 HTTP 框架。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            request_id=request.headers.get("x-request-id", ""),
        ).model_dump(),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理器：任何未捕获异常都回 500，且只返回固定文案。

    真实异常栈由 Starlette 记录到服务端日志；响应体不使用 ``str(exc)``，
    避免 MySQL 连接串、GitHub Token 等私有信息随 500 响应外泄。

    Returns:
        500 与 ``INTERNAL_ERROR`` 结构的 JSONResponse。
    """
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=INTERNAL_ERROR,
            message="Internal server error",
            request_id=request.headers.get("x-request-id", ""),
        ).model_dump(),
    )
