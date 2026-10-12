from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorResponse

REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"
INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
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
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            request_id=request.headers.get("x-request-id", ""),
        ).model_dump(),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=INTERNAL_ERROR,
            message="Internal server error",
            request_id=request.headers.get("x-request-id", ""),
        ).model_dump(),
    )
