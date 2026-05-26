from pathlib import Path

import pytest

from quant.providers.mock_provider import MockProvider
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository


def test_mock_provider_returns_trade_calendar():
    provider = MockProvider()

    calendar = provider.get_trade_calendar("2024-01-01", "2024-03-31")

    assert len(calendar) >= 40
    assert calendar[0].trade_date == "2024-01-02"
    assert calendar[0].is_open is True
    assert calendar[-1].next_trade_date is None


def test_mock_provider_returns_index_members_and_daily_bars():
    provider = MockProvider()

    members = provider.get_index_members(["CSI300"], "2024-01-31")
    bars = provider.get_daily_bars("2024-01-02", "2024-03-31")

    assert {member.index_code for member in members} == {"CSI300"}
    assert len(members) == 6
    assert any(bar.code == "600001" and bar.trade_date == "2024-01-02" for bar in bars)
    assert all(bar.available_date > bar.trade_date for bar in bars)


def test_mock_provider_available_date_skips_closed_dates():
    provider = MockProvider()

    bars = provider.get_daily_bars("2023-12-29", "2023-12-29")

    assert any(
        bar.code == "600001"
        and bar.trade_date == "2023-12-29"
        and bar.available_date == "2024-01-02"
        for bar in bars
    )


def test_mock_provider_returns_financial_and_valuation_data():
    provider = MockProvider()

    financials = provider.get_financials()
    valuations = provider.get_valuation("2024-01-02", "2024-03-31")

    assert any(item.code == "600001" and item.roe > 0 for item in financials)
    assert any(item.code == "600001" and item.pb > 0 for item in valuations)


def test_repository_syncs_mock_data(tmp_path: Path):
    db_path = tmp_path / "quant.duckdb"
    repository = QuantRepository(db_path)
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())

    result = pipeline.sync_data("2024-01-02", "2024-03-31", ["CSI300"])

    assert result["data_version"] == "mock-2024-q1"
    assert result["stock_count"] == 6
    assert result["daily_bar_count"] > 200
    assert repository.count_rows("stock_basic") == 6
    assert repository.count_rows("daily_bar") == result["daily_bar_count"]
    assert repository.latest_data_version() == "mock-2024-q1"


def test_repository_rejects_invalid_table_names(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")

    with pytest.raises(ValueError):
        repository.replace_table("stock_basic; drop table trade_calendar; --", [])

    assert repository.count_rows("trade_calendar") == 0


def test_repository_rejects_invalid_columns_and_preserves_existing_rows(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    repository.replace_table("stock_basic", [MockProvider().get_stock_basic()[0]])

    with pytest.raises(ValueError):
        repository.replace_table("stock_basic", [{"code": "600001", "unexpected": "bad"}])

    assert repository.count_rows("stock_basic") == 1
