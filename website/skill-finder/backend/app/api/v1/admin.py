"""管理端点（``/api/v1/admin``），全部要求 ``X-Admin-Key``。

两类操作：手动触发一次 Trending 采集、批量补全中文介绍。两者都只把工作丢进
BackgroundTasks 后立刻返回 202，真正的耗时逻辑在后台协程里跑，接口不等待结果。
采集先抢 MySQL 命名锁（见 :func:`app.core.scheduler.acquire_collection_lock`），
抢不到说明已有任务在跑，直接回 409 而不是排队；失败原因写在 ``collection_runs``，
由 ``/api/v1/stats`` 以固定提示对外暴露。
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import require_admin_key
from app.core.scheduler import acquire_collection_lock, run_collection

router = APIRouter(prefix="/admin", tags=["admin"])

# 与 app.api.errors 中的同名错误码保持一致，前端按 code 识别并发冲突。
COLLECTION_ALREADY_RUNNING = "COLLECTION_ALREADY_RUNNING"


@router.post("/collections", status_code=status.HTTP_202_ACCEPTED)
async def trigger_collection(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_key),
) -> dict[str, str]:
    """手动触发一次 GitHub Trending 采集。

    请求：``POST /api/v1/admin/collections``，无请求体，需 ``X-Admin-Key``。
    响应：202 ``{"status": "accepted"}``。

    先以 ``GET_LOCK(name, 0)`` 非阻塞抢锁，拿到锁才把采集放进后台任务，所以接口立即返回；
    锁被占用说明已有采集在跑，回 409。锁的释放由
    :func:`app.core.scheduler.run_collection` 的 finally 负责，异常路径也不会漏放。

    Args:
        background_tasks: FastAPI 注入，承载后台采集协程。
        _: 管理员密钥依赖，仅用于校验，不产生返回值。

    Raises:
        HTTPException: 已有采集在运行时 409（detail 含 ``COLLECTION_ALREADY_RUNNING``）；
            密钥错误由依赖抛 401。
    """
    lease = await acquire_collection_lock()
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": COLLECTION_ALREADY_RUNNING,
                "message": "A collection run is already in progress",
            },
        )
    background_tasks.add_task(run_collection, lease)
    return {"status": "accepted"}


@router.post("/introductions", status_code=status.HTTP_202_ACCEPTED)
async def trigger_introduction_backfill(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_key),
    category: str | None = Query(default=None, pattern="^(AGENT|SKILL|MCP|PLUGIN)$"),
    limit: int = Query(default=5, ge=1, le=100),
    order: str | None = Query(default=None, pattern="^daily$"),
) -> dict[str, str]:
    """为缺少中文介绍的历史仓库补全介绍，不重新采集榜单。

    请求：``POST /api/v1/admin/introductions?category=&limit=&order=``，需 ``X-Admin-Key``。
    响应：202 ``{"status": "accepted"}``；介绍在后台生成并写入 ``repositories.introduction``。

    Args:
        background_tasks: FastAPI 注入，承载补全协程。
        _: 管理员密钥依赖。
        category: 只补某个分类，留空表示不限；非法值由 Query 的 pattern 拦截为 422。
        limit: 单次最多处理 5-100 个仓库，默认 5。
        order: 传 ``daily`` 时按当日 Star 增量优先，其余按总 Star 排序。
    """
    background_tasks.add_task(
        run_introduction_backfill, category=category, limit=limit, order=order
    )
    return {"status": "accepted"}


async def run_introduction_backfill(
    *, category: str | None, limit: int, order: str | None
) -> None:
    """后台执行简介补全，把参数原样转交给介绍服务。

    采用函数内导入，避免 admin 路由在模块加载期就拉起介绍服务并读取模型配置。
    异常不在此捕获：后台任务失败由执行框架记录，接口早已返回 202，
    因此调用方不能靠这个响应判断补全是否真的成功。

    Args:
        category: 分类过滤，可为 ``None``。
        limit: 单次处理上限。
        order: 传 ``daily`` 表示按当日增量优先。
    """
    from app.services.introduction_service import run_introduction_backfill as backfill

    await backfill(category=category, limit=limit, order=order)
