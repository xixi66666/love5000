from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class TradeCalendarRow:
    """Open trading day within an inclusive provider date range."""

    trade_date: str
    is_open: bool
    prev_trade_date: Optional[str]
    next_trade_date: Optional[str]
    is_month_end: bool


@dataclass(frozen=True)
class StockBasicRow:
    code: str
    name: str
    exchange: str
    list_date: str
    delist_date: Optional[str]
    status: str
    industry: str
    is_st: bool


@dataclass(frozen=True)
class DailyBarRow:
    """Daily market data; available_date should be the next open trading day when possible."""

    trade_date: str
    code: str
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    volume: float
    amount: float
    turnover_rate: float
    adj_factor: float
    limit_up: float
    limit_down: float
    suspend_flag: bool
    available_date: str
    data_version: str


@dataclass(frozen=True)
class ValuationRow:
    trade_date: str
    code: str
    pe_ttm: float
    pb: float
    ps_ttm: float
    pcf_ttm: float
    dividend_yield: float
    total_market_value: float
    float_market_value: float
    available_date: str
    data_version: str


@dataclass(frozen=True)
class FinancialRow:
    code: str
    report_period: str
    announce_date: str
    available_date: str
    revenue: float
    net_profit: float
    deducted_net_profit: float
    operating_cash_flow: float
    roe: float
    roa: float
    gross_margin: float
    net_margin: float
    debt_ratio: float
    data_version: str


@dataclass(frozen=True)
class IndexMemberRow:
    index_code: str
    code: str
    effective_date: str
    expire_date: Optional[str]
    data_version: str


class DataProvider(Protocol):
    """Provider contract using inclusive start/end date ranges."""

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        """Return open trading days only for the inclusive date range."""
        raise NotImplementedError

    def get_stock_basic(self) -> List[StockBasicRow]:
        raise NotImplementedError

    def get_daily_bars(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[DailyBarRow]:
        raise NotImplementedError

    def get_valuation(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[ValuationRow]:
        raise NotImplementedError

    def get_financials(self) -> List[FinancialRow]:
        raise NotImplementedError

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        raise NotImplementedError
