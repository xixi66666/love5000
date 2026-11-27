"""采集锁与定时调度。

并发保护使用 MySQL 命名锁 ``GET_LOCK``（跨进程、跨机器有效）：抢锁时用独立连接与
``NullPool``，锁的生命周期跟这条连接绑定，因此 :class:`CollectionLockLease` 必须
在结束时释放并关闭连接，否则连接池外的连接会泄漏。

会话所有权：锁由本模块获取与释放；数据库会话由 :func:`run_collection` 用
``async_session_factory()`` 打开并在 ``async with`` 结束时关闭，采集服务只在阶段
边界提交事务。定时任务默认关闭（``scheduler_enabled``），开启后由 APScheduler
按 cron 在专用事件循环里跑。
"""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import settings
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

# MySQL 命名锁的名字，全局唯一；改名等于放弃与旧版本进程互斥，需要一并考虑部署顺序。
COLLECTION_LOCK_NAME = "skill_finder_collection"


class CollectionLockLease:
    """持有一条专用连接的锁租约。

    MySQL 命名锁属于“连接”而不是“事务”，因此租约里必须同时保存连接与临时引擎：
    释放时先 ``RELEASE_LOCK``，再关闭连接并 ``dispose`` 引擎，避免连接泄漏。
    租约只应由 :func:`acquire_collection_lock` 创建，并且只释放一次。
    """

    def __init__(self, connection: AsyncConnection, engine: Any) -> None:
        self._connection = connection
        self._engine = engine

    async def release(self) -> None:
        """释放命名锁并关闭专用连接。

        释放语句本身失败（连接已被服务端断开等）时仍然执行 finally 里的关闭，
        因此不会因为一次错误就让连接无法回收；重复调用只会再次关闭已关闭的连接。
        """
        try:
            await self._connection.execute(sa.text(f"SELECT RELEASE_LOCK('{COLLECTION_LOCK_NAME}')"))
        finally:
            await self._connection.close()
            await self._engine.dispose()


async def acquire_collection_lock() -> CollectionLockLease | None:
    """非阻塞地抢占采集命名锁。

    使用 ``GET_LOCK(name, 0)``：立即返回，拿不到就说明别的进程/实例正在采集。
    抢锁过程出错时会先关连接再抛，避免把连接留在池外。

    Returns:
        拿到锁时返回 :class:`CollectionLockLease`；已被占用时返回 ``None`` 并关掉
        本次连接，调用方据此返回 409 或跳过本轮。

    Raises:
        Exception: 连接数据库失败等底层错误原样上抛，由调用方决定状态码。
    """
    engine = create_async_engine(settings.database_url, poolclass=sa.pool.NullPool)
    connection = await engine.connect()
    try:
        result = await connection.execute(
            sa.text(f"SELECT GET_LOCK('{COLLECTION_LOCK_NAME}', 0)")
        )
        acquired = result.scalar() == 1
    except Exception:
        await connection.close()
        await engine.dispose()
        raise
    if not acquired:
        await connection.close()
        await engine.dispose()
        return None
    return CollectionLockLease(connection, engine)


async def run_collection(lease: CollectionLockLease | None) -> None:
    """在已持有的锁租约内执行一轮采集，退出时必定释放锁。

    延迟导入采集相关模块：``app.main`` 导入本模块时不应连带加载 Scrapling 与
    GitHub 客户端，缩短启动时间也避免循环导入。

    会话由本函数打开并关闭（``async with async_session_factory()``），采集服务只在
    阶段边界提交；这里不捕获采集异常——接口早已返回 202，异常由后台任务框架记录，
    任务状态已由采集服务写成 ``FAILED``。

    Args:
        lease: 命名锁租约，``None`` 表示调用方没有抢到锁（仍会执行采集并在结束时跳过释放）。
    """
    from app.collector.github_client import GitHubClient
    from app.collector.service import CollectionService
    from app.collector.trending import TrendingScraper
    from app.repositories.collection_runs import CollectionRunStore
    from app.repositories.repositories import RepositoryStore
    from app.repositories.snapshots import SnapshotStore
    from app.repositories.trending import TrendingStore

    try:
        async with (
            async_session_factory() as session,
            GitHubClient(
                token=settings.github_token.get_secret_value(), proxy=settings.trending_proxy
            ) as github_client,
        ):
            service = CollectionService(
                scraper=TrendingScraper(proxy=settings.trending_proxy),
                github_client=github_client,
                repository_store=RepositoryStore(session),
                snapshot_store=SnapshotStore(session),
                trending_store=TrendingStore(session),
                run_store=CollectionRunStore(session),
                session=session,
                business_timezone=settings.business_timezone,
                top_n=settings.trending_top_n,
                ai_keywords=settings.trending_ai_keywords,
                trigger_type="manual",
            )
            result = await service.run()
            logger.info(
                "collection run %s finished with status %s",
                result.run_id,
                result.status,
            )
    finally:
        if lease is not None:
            await lease.release()


def _scheduler_job() -> None:
    """APScheduler 的同步回调：为新的一轮采集创建独立事件循环。

    AsyncIOScheduler 在这个项目里跑的是同步入口，因此用 ``asyncio.run`` 建立一次性
    事件循环；这也保证每轮采集的连接池与协程生命周期互相隔离。
    """
    import asyncio

    asyncio.run(_scheduled_collection())


async def _scheduled_collection() -> None:
    """定时采集入口：抢不到锁就安静跳过，不排队也不报错。

    上一轮还没跑完时直接返回并记一条日志，避免定时任务堆积。
    """
    lease = await acquire_collection_lock()
    if lease is None:
        logger.info("collection skipped: another run holds the lock")
        return
    await run_collection(lease)


def start_scheduler() -> Any:
    """按配置创建调度器，仅在启用时注册并启动采集任务。

    未启用时仍返回一个未启动的调度器实例，调用方可以统一在关闭阶段调用
    ``shutdown``；``replace_existing=True`` 让重复启动不会注册出多个同名任务。

    Returns:
        AsyncIOScheduler 实例（可能未启动）。
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone=settings.business_timezone)
    if settings.scheduler_enabled:
        scheduler.add_job(
            _scheduler_job,
            "cron",
            id="collection",
            replace_existing=True,
            **(_parse_cron(settings.collection_cron)),
        )
        scheduler.start()
    return scheduler


def _parse_cron(expr: str) -> dict[str, str]:
    """把五段式 cron 表达式拆成 APScheduler 的关键字参数。

    Args:
        expr: ``分 时 日 月 周`` 五段，例如 ``0 2 * * *``。

    Returns:
        ``minute/hour/day/month/day_of_week`` 五个键；段数不足时抛 ``ValueError``，
        让配置错误在启动阶段暴露。
    """
    minute, hour, day, month, day_of_week = expr.split()
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }
