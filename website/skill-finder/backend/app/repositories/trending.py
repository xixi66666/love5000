"""``trending_entries`` 表（三个周期的当前榜单）的访问对象。

榜单是“当前快照”语义：每个周期整段替换（先删后插），因此这里不提供增量更新。
唯一键 ``(period, repository_id)`` 防止同一仓库在一个周期里出现两次。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrendingEntry


@dataclass(frozen=True)
class TrendingEntryValue:
    """榜单写入时的一行，与 ORM 解耦。

    Attributes:
        repository_id: ``repositories.id``。
        rank_position: 榜单名次，从 1 开始。
        stars_gained: 周期内新增 Star，列表排序与首页展示都用它。
        stars_total: 页面显示的总 Star；缺失时调用方会用库中值兜底。
    """

    repository_id: int
    rank_position: int
    stars_gained: int
    stars_total: int


class TrendingStore:
    """替换某个周期的当前 Top N 榜单。

    先 ``DELETE`` 该周期的全部旧行，再批量插入新行；``entries`` 为空时只删除不插入，
    但采集服务在“入选仓库全部补全失败”时不会调用本方法，以免把上一轮榜单清空。
    删除与插入在同一个事务里，由调用方提交后整段切换才对其他连接可见。
    """

    def __init__(self, session: AsyncSession) -> None:
        """只保存会话引用：删除与插入都在调用方的事务里完成。

        Args:
            session: 调用方打开的会话，本仓储不提交也不关闭。
        """
        self._session = session

    async def replace_period(
        self,
        period: str,
        entries: list[TrendingEntryValue],
        fetched_at: datetime,
    ) -> None:
        """用新榜单替换指定周期的全部旧行。

        Args:
            period: ``daily`` / ``weekly`` / ``monthly``。
            entries: 新榜单；为空表示清空该周期（正常采集不会这么调用）。
            fetched_at: 本轮抓取时间（UTC），写入每行便于判断榜单新鲜度。
        """
        await self._session.execute(
            delete(TrendingEntry).where(TrendingEntry.period == period)
        )
        if not entries:
            return
        await self._session.execute(
            insert(TrendingEntry),
            [
                {
                    "repository_id": entry.repository_id,
                    "period": period,
                    "rank_position": entry.rank_position,
                    "stars_gained": entry.stars_gained,
                    "stars_total": entry.stars_total,
                    "fetched_at": fetched_at,
                }
                for entry in entries
            ],
        )
