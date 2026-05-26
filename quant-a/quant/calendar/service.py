from typing import List

from quant.storage.repository import QuantRepository


class TradingCalendarService:
    def __init__(self, repository: QuantRepository):
        self.repository = repository

    def next_trade_date(self, trade_date: str) -> str:
        rows = self.repository.fetch_dicts(
            "select next_trade_date from trade_calendar where trade_date = ?",
            [trade_date],
        )
        if not rows or not rows[0]["next_trade_date"]:
            raise ValueError(f"No next trade date for {trade_date}")
        return str(rows[0]["next_trade_date"])

    def month_end_trade_dates(self, start_date: str, end_date: str) -> List[str]:
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
