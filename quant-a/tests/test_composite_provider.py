from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)
from quant.providers.factory import create_provider
from quant.providers.tushare_akshare_provider import TushareAkshareProvider


class PrimaryProvider:
    name = "tushare"
    data_version = "tushare-v1"

    def __init__(self):
        self.daily_calls = []

    def get_trade_calendar(self, start_date, end_date):
        return [
            TradeCalendarRow("2024-01-02", True, None, "2024-01-03", False),
            TradeCalendarRow("2024-01-03", True, "2024-01-02", None, False),
        ]

    def get_stock_basic(self):
        return [
            StockBasicRow("600001", "浦江制造", "SH", "2010-01-01", None, "listed", "工业", False),
            StockBasicRow("000001", "南方银行", "SZ", "1991-04-03", None, "listed", "金融", False),
        ]

    def get_daily_bars(self, start_date, end_date, codes=None):
        self.daily_calls.append(list(codes or []))
        return [
            DailyBarRow(
                "2024-01-02",
                "600001",
                10.0,
                10.5,
                9.8,
                10.2,
                10.1,
                1200.0,
                12345.0,
                1.2,
                1.0,
                11.1,
                9.1,
                False,
                "2024-01-03",
                "tushare-v1",
            )
        ]

    def get_valuation(self, start_date, end_date, codes=None):
        return [
            ValuationRow(
                "2024-01-02",
                "600001",
                10.0,
                1.0,
                2.0,
                8.0,
                0.02,
                100.0,
                80.0,
                "2024-01-03",
                "tushare-v1",
            )
        ]

    def get_financials(self):
        return [
            FinancialRow(
                "600001",
                "2023-12-31",
                "2024-01-15",
                "2024-01-16",
                100.0,
                10.0,
                9.0,
                12.0,
                0.1,
                0.05,
                0.3,
                0.1,
                0.4,
                "tushare-v1",
            )
        ]

    def get_index_members(self, index_codes, trade_date):
        return [
            IndexMemberRow(index_codes[0], "600001", trade_date, None, "tushare-v1"),
        ]


class FallbackProvider:
    name = "akshare"
    data_version = "akshare-v1"

    def get_stock_basic(self):
        return [
            StockBasicRow("000001", "南方银行", "SZ", "1991-04-03", None, "listed", "金融", False),
        ]

    def get_daily_bars(self, start_date, end_date, codes=None):
        return [
            DailyBarRow(
                "2024-01-02",
                "000001",
                20.0,
                20.5,
                19.8,
                20.2,
                20.1,
                2200.0,
                22345.0,
                1.3,
                1.0,
                22.1,
                18.1,
                False,
                "2024-01-03",
                "akshare-v1",
            )
        ]


def test_provider_factory_creates_tushare_akshare_provider():
    provider = create_provider({"provider": {"active": "tushare_akshare"}})

    assert provider.name == "tushare_akshare"


def test_composite_provider_uses_akshare_only_for_failed_daily_codes():
    provider = TushareAkshareProvider(PrimaryProvider(), FallbackProvider())

    rows = provider.get_daily_bars("2024-01-02", "2024-01-03", codes=["600001", "000001"])

    assert [row.code for row in rows] == ["600001", "000001"]
    assert provider.fallback_count == 1
    assert provider.failed_code_count == 0


def test_composite_provider_does_not_fallback_valuation_or_financials():
    provider = TushareAkshareProvider(PrimaryProvider(), FallbackProvider())

    valuations = provider.get_valuation("2024-01-02", "2024-01-03", codes=["600001", "000001"])
    financials = provider.get_financials()

    assert [row.code for row in valuations] == ["600001"]
    assert [row.code for row in financials] == ["600001"]


def test_composite_provider_expands_all_market_members_from_stock_basic():
    provider = TushareAkshareProvider(PrimaryProvider(), FallbackProvider())

    members = provider.get_index_members(["ALL"], "2024-01-02")

    assert [row.code for row in members] == ["600001", "000001"]
    assert all(row.index_code == "ALL" for row in members)
