"""``star_snapshots`` 表（每日 Star 快照）的访问对象。

每天每个仓库只应有一行：写入使用 ``ON DUPLICATE KEY UPDATE`` 覆盖当天数值，
因此同一天多次采集不会产生重复行。只 flush 不提交，事务边界由调用方掌握。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StarSnapshot


class SnapshotStore:
    """Star 快照仓储，只提供“按天写覆盖”的能力。

    详情页的 30 天曲线与增量回退都读这张表，因此写入必须幂等。
    """

    def __init__(self, session: AsyncSession) -> None:
        """只保存会话引用：写覆盖随采集服务的阶段提交一起生效。

        Args:
            session: 调用方打开的会话，本仓储不提交也不关闭。
        """
        self._session = session

    async def upsert_daily(
        self, repository_id: int, snapshot_date: date, stars_count: int
    ) -> None:
        """写入或覆盖某个仓库某一天的 Star 数。

        唯一键 ``(repository_id, snapshot_date)`` 命中时只更新 ``stars_count``，
        不重建行，避免历史 id 变动影响引用。

        Args:
            repository_id: ``repositories.id``（不是 github_id）。
            snapshot_date: 业务时区下的日期，与 ``trending_entries`` 口径一致。
            stars_count: 当日总 Star 数。
        """
        stmt = insert(StarSnapshot).values(
            repository_id=repository_id,
            snapshot_date=snapshot_date,
            stars_count=stars_count,
        )
        stmt = stmt.on_duplicate_key_update(stars_count=stmt.inserted["stars_count"])
        await self._session.execute(stmt)
