import sys
import types

import pytest

from quant.providers.tushare_provider import TushareProvider


class FakePro:
    def __init__(self):
        self.calls = []

    def stock_basic(self, **kwargs):
        self.calls.append(("stock_basic", kwargs))
        return [
            {
                "ts_code": "000001.SZ",
                "name": "平安银行",
                "exchange": "SZSE",
                "list_date": "19910403",
                "delist_date": "",
                "list_status": "L",
                "industry": "银行",
            }
        ]

    def trade_cal(self, **kwargs):
        self.calls.append(("trade_cal", kwargs))
        return [
            {"cal_date": "20240102", "is_open": 1, "pretrade_date": "20231229"},
            {"cal_date": "20240103", "is_open": 1, "pretrade_date": "20240102"},
        ]

    def daily(self, **kwargs):
        self.calls.append(("daily", kwargs))
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "pre_close": 10.1,
                "vol": 1200.0,
                "amount": 12345.0,
            }
        ]

    def daily_basic(self, **kwargs):
        self.calls.append(("daily_basic", kwargs))
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "pe_ttm": 6.5,
                "pb": 0.7,
                "ps_ttm": 1.1,
                "pcf": 4.2,
                "dv_ttm": 0.03,
                "total_mv": 100000.0,
                "circ_mv": 80000.0,
            }
        ]


def install_fake_tushare(monkeypatch):
    fake_pro = FakePro()
    module = types.SimpleNamespace(pro_api=lambda token, timeout=None: fake_pro)
    monkeypatch.setitem(sys.modules, "tushare", module)
    return fake_pro


def test_missing_token_is_reported_when_method_is_called(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    install_fake_tushare(monkeypatch)

    provider = TushareProvider()

    with pytest.raises(RuntimeError, match="Tushare token is required. Set TUSHARE_TOKEN before using provider.active=tushare."):
        provider.get_stock_basic()


def test_missing_dependency_is_reported_after_token_check(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")

    def fail_import(name):
        if name == "tushare":
            raise ImportError("missing tushare")
        return __import__(name)

    monkeypatch.setattr("quant.providers.tushare_provider.importlib.import_module", fail_import)

    provider = TushareProvider()

    with pytest.raises(RuntimeError, match="Tushare is not installed. Run: python -m pip install -r requirements.txt"):
        provider.get_stock_basic()


def test_stock_basic_calls_tushare_and_maps_rows(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_pro = install_fake_tushare(monkeypatch)

    rows = TushareProvider().get_stock_basic()

    assert fake_pro.calls[0] == ("stock_basic", {"exchange": "", "list_status": "L", "fields": "ts_code,name,exchange,list_date,delist_date,list_status,industry"})
    assert rows[0].code == "000001"
    assert rows[0].name == "平安银行"
    assert rows[0].exchange == "SZSE"
    assert rows[0].list_date == "1991-04-03"
    assert rows[0].status == "listed"
    assert rows[0].industry == "银行"


def test_trade_calendar_calls_tushare_and_returns_open_days(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_pro = install_fake_tushare(monkeypatch)

    rows = TushareProvider().get_trade_calendar("2024-01-02", "2024-01-03")

    assert fake_pro.calls[0] == ("trade_cal", {"exchange": "", "start_date": "20240102", "end_date": "20240103"})
    assert [row.trade_date for row in rows] == ["2024-01-02", "2024-01-03"]
    assert rows[0].prev_trade_date == "2023-12-29"
    assert rows[0].next_trade_date == "2024-01-03"
    assert rows[-1].next_trade_date is None


def test_daily_bars_calls_tushare_and_maps_rows(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_pro = install_fake_tushare(monkeypatch)

    rows = TushareProvider().get_daily_bars("2024-01-02", "2024-01-02")

    assert fake_pro.calls[0] == ("daily", {"start_date": "20240102", "end_date": "20240102"})
    assert rows[0].trade_date == "2024-01-02"
    assert rows[0].code == "000001"
    assert rows[0].close == 10.2
    assert rows[0].volume == 1200.0
    assert rows[0].available_date == "2024-01-03"
    assert rows[0].data_version == "tushare-v1"


def test_valuation_calls_tushare_and_maps_rows(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_pro = install_fake_tushare(monkeypatch)

    rows = TushareProvider().get_valuation("2024-01-02", "2024-01-02")

    assert fake_pro.calls[0] == ("daily_basic", {"start_date": "20240102", "end_date": "20240102"})
    assert rows[0].trade_date == "2024-01-02"
    assert rows[0].code == "000001"
    assert rows[0].pe_ttm == 6.5
    assert rows[0].pcf_ttm == 4.2
    assert rows[0].dividend_yield == 0.03


def test_permission_gated_methods_explain_future_extension(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    install_fake_tushare(monkeypatch)
    provider = TushareProvider()

    with pytest.raises(NotImplementedError, match="Tushare financial endpoints require matching Tushare permissions"):
        provider.get_financials()

    with pytest.raises(NotImplementedError, match="Tushare index member endpoints require matching Tushare permissions"):
        provider.get_index_members(["000300.SH"], "2024-01-02")
