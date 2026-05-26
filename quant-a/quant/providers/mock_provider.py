from datetime import date, timedelta
from typing import List

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


class MockProvider:
    data_version = "mock-2024-q1"
    closed_dates = {"2024-01-01"}

    codes = [
        ("600001", "浦江制造", "SH", "2010-01-01", "工业", False),
        ("600002", "海岳能源", "SH", "2012-05-10", "能源", False),
        ("600003", "星河科技", "SH", "2016-03-18", "科技", False),
        ("000001", "南方银行", "SZ", "1991-04-03", "金融", False),
        ("000002", "长风地产", "SZ", "2001-09-21", "地产", False),
        ("000003", "华康医药", "SZ", "2018-07-11", "医药", False),
    ]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = []
        current = start
        while current <= end:
            if current.weekday() < 5 and current.isoformat() not in self.closed_dates:
                days.append(current.isoformat())
            current += timedelta(days=1)

        rows = []
        for index, day in enumerate(days):
            next_day = days[index + 1] if index + 1 < len(days) else None
            rows.append(TradeCalendarRow(
                trade_date=day,
                is_open=True,
                prev_trade_date=days[index - 1] if index > 0 else None,
                next_trade_date=next_day,
                is_month_end=next_day is None or next_day[:7] != day[:7],
            ))
        return rows

    def get_stock_basic(self) -> List[StockBasicRow]:
        return [
            StockBasicRow(code, name, exchange, list_date, None, "listed", industry, is_st)
            for code, name, exchange, list_date, industry, is_st in self.codes
        ]

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        rows = []
        for index_code in index_codes:
            for code, *_ in self.codes:
                rows.append(IndexMemberRow(index_code, code, "2024-01-01", None, self.data_version))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        calendar = self.get_trade_calendar(start_date, end_date)
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            base = 10.0 + code_index * 3
            for day_index, cal in enumerate(calendar):
                close = round(base + day_index * (0.05 + code_index * 0.01), 2)
                pre_close = round(close - 0.05, 2)
                rows.append(DailyBarRow(
                    trade_date=cal.trade_date,
                    code=code,
                    open=round(close - 0.02, 2),
                    high=round(close + 0.15, 2),
                    low=round(close - 0.20, 2),
                    close=close,
                    pre_close=pre_close,
                    volume=1000000 + code_index * 100000,
                    amount=(1000000 + code_index * 100000) * close,
                    turnover_rate=1.5 + code_index * 0.2,
                    adj_factor=1.0,
                    limit_up=round(pre_close * 1.1, 2),
                    limit_down=round(pre_close * 0.9, 2),
                    suspend_flag=False,
                    available_date=self._available_date(cal),
                    data_version=self.data_version,
                ))
        return rows

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        calendar = self.get_trade_calendar(start_date, end_date)
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            for cal in calendar:
                rows.append(ValuationRow(
                    trade_date=cal.trade_date,
                    code=code,
                    pe_ttm=12.0 + code_index * 2,
                    pb=1.1 + code_index * 0.2,
                    ps_ttm=1.8 + code_index * 0.3,
                    pcf_ttm=9.0 + code_index,
                    dividend_yield=0.01 + code_index * 0.002,
                    total_market_value=20000000000 + code_index * 3000000000,
                    float_market_value=15000000000 + code_index * 2500000000,
                    available_date=self._available_date(cal),
                    data_version=self.data_version,
                ))
        return rows

    def get_financials(self) -> List[FinancialRow]:
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            rows.append(FinancialRow(
                code=code,
                report_period="2023-12-31",
                announce_date="2024-01-15",
                available_date="2024-01-16",
                revenue=1000000000 + code_index * 90000000,
                net_profit=120000000 + code_index * 10000000,
                deducted_net_profit=110000000 + code_index * 9000000,
                operating_cash_flow=140000000 + code_index * 8000000,
                roe=0.08 + code_index * 0.015,
                roa=0.04 + code_index * 0.006,
                gross_margin=0.25 + code_index * 0.02,
                net_margin=0.12 + code_index * 0.01,
                debt_ratio=0.55 - code_index * 0.03,
                data_version=self.data_version,
            ))
        return rows

    def _available_date(self, calendar_row: TradeCalendarRow) -> str:
        if calendar_row.next_trade_date:
            return calendar_row.next_trade_date

        current = date.fromisoformat(calendar_row.trade_date) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()
