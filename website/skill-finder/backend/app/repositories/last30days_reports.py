"""``last30days_reports`` 表（近 30 天研究结果）的访问对象。

按 ``direction`` 一方向一行覆盖写入；写入以调用方的事务为准（本模块只 flush），
刷新接口在 ``refresh_ranking`` 内提交。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Last30DaysReport


class Last30DaysReportStore:
    """近 30 天研究结果仓储。

    只读写 ``direction`` 指定的那一行，不缓存、不持有连接；会话由调用方提供。
    """

    def __init__(self, session: AsyncSession) -> None:
        """只保存会话引用：提交由 ``refresh_ranking`` 负责，关闭由请求依赖负责。

        Args:
            session: 调用方打开的会话，本仓储不提交也不关闭。
        """
        self._session = session

    async def get(self, direction: str) -> Last30DaysReport | None:
        """按方向读取已落库的研究结果。

        Args:
            direction: ``agent`` 或 ``skill``。

        Returns:
            对应的行；从未抓取过时为 ``None``，调用方据此返回空榜单。
        """
        result = await self._session.execute(
            select(Last30DaysReport).where(Last30DaysReport.direction == direction)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        direction: str,
        status: str,
        payload: dict[str, Any],
        message: str | None,
        fetched_at: datetime,
    ) -> None:
        """写入或覆盖某个方向的结果。

        先查再改而不是用 ``ON DUPLICATE KEY UPDATE``：``direction`` 是主键，行数很少，
        这样能同时更新 ``updated_at`` 的 ORM 默认值，代码也更直白。

        Args:
            direction: ``agent`` 或 ``skill``。
            status: 结果状态（成功或降级）。
            payload: 完整结果的 JSON 结构。
            message: 降级说明，例如某个来源超时；正常时为 ``None``。
            fetched_at: 本次抓取时间（UTC）。
        """
        report = await self.get(direction)
        if report is None:
            report = Last30DaysReport(
                direction=direction,
                status=status,
                payload=payload,
                message=message,
                fetched_at=fetched_at,
            )
            self._session.add(report)
        else:
            report.status = status
            report.payload = payload
            report.message = message
            report.fetched_at = fetched_at
        await self._session.flush()
