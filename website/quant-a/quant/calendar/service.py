"""交易日历查询服务 `TradingCalendarService`。

日历本身由 Provider 同步进 DuckDB 的 `trade_calendar` 表（字段 `trade_date`、
`is_open`、`prev_trade_date`、`next_trade_date`、`is_month_end`）。本服务只读表、
不推算交易日，因此法定节假日是否准确完全取决于数据源；Provider 侧只按工作日近似
（见 `AkShareProvider`），节假日缺失时可能把休市日当成交易日。

使用方是再平衡调度与回测：`next_trade_date` 保证信号在下一个交易日才成交，
`month_end_trade_dates` 提供按月调仓的信号日，两者共同避免使用未来价格。
"""

from typing import List

from quant.storage.repository import QuantRepository


class TradingCalendarService:
    """从本地 `trade_calendar` 表读取下一个交易日与月末交易日。"""

    def __init__(self, repository: QuantRepository):
        """注入本地仓储；服务无状态，可在请求之间复用。

        Args:
            repository: 已初始化表的 `QuantRepository`，日历表为空时查询会得到空结果。
        """
        self.repository = repository

    def next_trade_date(self, trade_date: str) -> str:
        """返回给定交易日的下一个开市日。

        Args:
            trade_date: 形如 `2024-01-31` 的交易日字符串。

        Returns:
            下一个交易日的 ISO 日期字符串。

        Raises:
            ValueError: 日历中没有该日期，或它是同步窗口的最后一天（`next_trade_date`
                为空）。回测调度依赖这个异常跳过无法在窗口内执行完的信号，而不是
                退化成同日成交。
        """
        rows = self.repository.fetch_dicts(
            "select next_trade_date from trade_calendar where trade_date = ?",
            [trade_date],
        )
        if not rows or not rows[0]["next_trade_date"]:
            raise ValueError(f"No next trade date for {trade_date}")
        return str(rows[0]["next_trade_date"])

    def month_end_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """列出区间内被标记为月末的交易日。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            升序排列的月末交易日列表。`is_month_end` 由数据源计算（通常是"下一个
            开市日已跨月"），因此当同步窗口在月末前被截断时，窗口内最后一天也会被
            标记为月末；这不影响回测，因为执行日仍由 `next_trade_date` 决定。
        """
        rows = self.repository.fetch_dicts(
            """
            select trade_date
            from trade_calendar
            where trade_date between ? and ?
              and is_month_end = true
            order by trade_date
            """,
            [start_date, end_date],
        )
        return [str(row["trade_date"]) for row in rows]
