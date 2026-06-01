import sys
import types

import pytest

from quant.providers.akshare_provider import AkShareProvider


class FakeDataFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


def install_fake_akshare(monkeypatch, stock_rows=None, hist_by_code=None):
    fake_akshare = types.SimpleNamespace()

    def stock_info_a_code_name():
        return FakeDataFrame(stock_rows or [])

    def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
        value = (hist_by_code or {}).get(symbol, [])
        if isinstance(value, Exception):
            raise value
        return FakeDataFrame(value)

    fake_akshare.stock_info_a_code_name = stock_info_a_code_name
    fake_akshare.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    return fake_akshare


def test_provider_raises_clear_error_when_akshare_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "akshare", None)
    provider = AkShareProvider()

    with pytest.raises(RuntimeError, match="AkShare is not installed"):
        provider.get_stock_basic()


def test_get_stock_basic_parses_code_name_and_defaults(monkeypatch):
    install_fake_akshare(
        monkeypatch,
        stock_rows=[
            {"code": "600001", "name": "浦江制造"},
            {"code": "000001", "name": "*ST南方"},
            {"code": "430001", "name": "北证科技"},
        ],
    )

    rows = AkShareProvider().get_stock_basic()

    assert [row.code for row in rows] == ["600001", "000001", "430001"]
    assert rows[0].exchange == "SH"
    assert rows[1].exchange == "SZ"
    assert rows[2].exchange == "BJ"
    assert all(row.list_date == "1990-01-01" for row in rows)
    assert all(row.industry == "未分类" for row in rows)
    assert rows[1].is_st is True
    assert all(row.status == "listed" for row in rows)


def test_get_daily_bars_parses_rows_and_isolates_single_stock_errors(monkeypatch):
    install_fake_akshare(
        monkeypatch,
        stock_rows=[
            {"code": "600001", "name": "浦江制造"},
            {"code": "000001", "name": "南方银行"},
        ],
        hist_by_code={
            "600001": [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "收盘": 10.5,
                    "最高": 10.8,
                    "最低": 9.9,
                    "成交量": 120000,
                    "成交额": 1260000,
                    "换手率": 1.2,
                    "涨跌幅": 5.0,
                }
            ],
            "000001": RuntimeError("remote timeout"),
        },
    )
    provider = AkShareProvider()

    rows = provider.get_daily_bars("2024-01-02", "2024-01-02")

    assert len(rows) == 1
    assert rows[0].code == "600001"
    assert rows[0].trade_date == "2024-01-02"
    assert rows[0].open == 10.0
    assert rows[0].close == 10.5
    assert rows[0].pre_close == 10.0
    assert rows[0].available_date == "2024-01-03"
    assert rows[0].data_version == "akshare-20240102"
    assert rows[0].limit_up == 11.0
    assert rows[0].limit_down == 9.0
    assert provider.errors == [{"code": "000001", "message": "remote timeout"}]


def test_neutral_valuation_and_financials_are_labeled_as_derived(monkeypatch):
    install_fake_akshare(
        monkeypatch,
        stock_rows=[{"code": "600001", "name": "浦江制造"}],
        hist_by_code={
            "600001": [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "收盘": 10.5,
                    "最高": 10.8,
                    "最低": 9.9,
                    "成交量": 120000,
                    "成交额": 1260000,
                    "换手率": 1.2,
                    "涨跌幅": 5.0,
                }
            ]
        },
    )
    provider = AkShareProvider()

    valuations = provider.get_valuation("2024-01-02", "2024-01-02")
    financials = provider.get_financials()

    assert valuations[0].code == "600001"
    assert valuations[0].data_version == "akshare-derived-neutral-20240102"
    assert valuations[0].available_date == "2024-01-03"
    assert financials[0].code == "600001"
    assert financials[0].roe > 0
    assert financials[0].data_version == "akshare-derived-neutral-financial"


def test_get_index_members_falls_back_to_full_market_and_records_warning(monkeypatch):
    install_fake_akshare(
        monkeypatch,
        stock_rows=[
            {"code": "600001", "name": "浦江制造"},
            {"code": "000001", "name": "南方银行"},
        ],
    )
    provider = AkShareProvider()

    rows = provider.get_index_members(["ALL", "CSI300"], "2024-01-31")

    assert len(rows) == 4
    assert {row.index_code for row in rows} == {"ALL", "CSI300"}
    assert all(row.effective_date == "2024-01-31" for row in rows)
    assert any("CSI300" in warning for warning in provider.warnings)
