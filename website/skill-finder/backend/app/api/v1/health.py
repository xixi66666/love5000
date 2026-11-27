"""``/api/v1`` 下的存活探针。

与 ``app.main`` 里的统一健康检查 ``GET /api/health``（返回 ``success`` / ``service``）
区分：这里的响应体是 ``{"status": "ok"}``，供旧调用方或探活脚本使用。
两者都不访问数据库与外部依赖，因此数据库故障时仍返回 200。
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """返回进程存活标记。

    请求：``GET /api/v1/health``。
    响应：200 ``{"status": "ok"}``；不检查数据库、GitHub 或模型网关，
    依赖不可用时依然为 200，避免把“依赖挂了”误报成“进程挂了”。
    """
    return {"status": "ok"}
