"""``collection_runs`` 表（采集任务运行记录）的访问对象。

写入只 ``flush`` 不 ``commit``：采集服务需要先提交 ``RUNNING`` 让其他连接看到任务已
开始，再在结束时提交终态，提交时机必须由它掌握。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionRun


class CollectionRunStore:
    """采集任务记录仓储。

    不持有连接，只持有调用方传入的会话；因此可以配合采集服务的长事务，也可以
    在请求里做一次性只读查询（``/api/v1/collections/refresh`` 的冷却判断）。
    """

    def __init__(self, session: AsyncSession) -> None:
        """只保存会话引用：打开、提交与关闭都由调用方负责。

        Args:
            session: 调用方打开的会话，本仓储既不提交也不关闭。
        """
        self._session = session

    async def create(self, trigger_type: str) -> CollectionRun:
        """插入一条 ``RUNNING`` 任务并取回主键。

        Args:
            trigger_type: 触发来源，``manual``（接口/脚本触发）或 ``scheduled``（定时）。

        Returns:
            已 flush 的 ORM 对象，``id`` 可用；提交由调用方负责。
        """
        run = CollectionRun(
            status="RUNNING",
            trigger_type=trigger_type,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def finish(
        self,
        run: CollectionRun,
        *,
        status: str,
        query_count: int,
        discovered_count: int,
        updated_count: int,
        failed_count: int,
        rate_limit_remaining: int | None,
        rate_limit_reset_at: datetime | None,
        error_summary: str | None,
    ) -> None:
        """把一轮采集的终态与计数写回任务行。

        只在内存对象上赋值 + flush，仍未提交；调用方（采集服务的 ``_finish``）随后
        ``commit``，保证“任务状态”和“本轮已写入的榜单”要么都可见，要么都不可见。

        Args:
            run: :meth:`create` 返回的任务对象。
            status: ``SUCCESS`` / ``PARTIAL`` / ``FAILED``。
            query_count: 期望抓取的周期数。
            discovered_count: 三个榜单页累计解析条数。
            updated_count: 成功写入的仓库数。
            failed_count: 补全失败或被过滤的仓库数。
            rate_limit_remaining: 结束时 GitHub 剩余额度，未知为 ``None``。
            rate_limit_reset_at: 额度重置时间，未知为 ``None``。
            error_summary: 失败/警告摘要，供服务端排查与固定提示映射。
        """
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.query_count = query_count
        run.discovered_count = discovered_count
        run.updated_count = updated_count
        run.failed_count = failed_count
        run.rate_limit_remaining = rate_limit_remaining
        run.rate_limit_reset_at = rate_limit_reset_at
        run.error_summary = error_summary
        await self._session.flush()

    async def latest(self) -> CollectionRun | None:
        """取最近开始的一次任务。

        刷新接口用它判断冷却与冷却豁免：最新任务若为 ``FAILED`` 允许立即重试。

        Returns:
            ``started_at`` 最大的一行；没有任何记录时为 ``None``。
        """
        result = await self._session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
