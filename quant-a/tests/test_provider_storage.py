from pathlib import Path

import pytest

from quant.providers.mock_provider import MockProvider
from quant.providers.factory import create_provider
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository


class CountingMockProvider(MockProvider):
    def __init__(self):
        self.stock_basic_calls = 0
        self.daily_bar_calls = 0
        self.valuation_calls = 0

    def get_stock_basic(self):
        self.stock_basic_calls += 1
        return super().get_stock_basic()

    def get_daily_bars(self, start_date, end_date, codes=None):
        self.daily_bar_calls += 1
        return super().get_daily_bars(start_date, end_date, codes=codes)

    def get_valuation(self, start_date, end_date, codes=None):
        self.valuation_calls += 1
        return super().get_valuation(start_date, end_date, codes=codes)


def test_mock_provider_returns_trade_calendar():
    provider = MockProvider()

    calendar = provider.get_trade_calendar("2024-01-01", "2024-03-31")

    assert len(calendar) >= 40
    assert calendar[0].trade_date == "2024-01-02"
    assert calendar[0].is_open is True
    assert calendar[-1].next_trade_date is None


def test_provider_factory_creates_mock_provider_from_config():
    provider = create_provider({"provider": {"active": "mock"}})

    assert isinstance(provider, MockProvider)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider: unknown"):
        create_provider({"provider": {"active": "unknown"}})


def test_provider_factory_creates_akshare_provider_without_loading_market_data():
    provider = create_provider({
        "provider": {
            "active": "akshare",
            "akshare": {"timeout_seconds": 23},
        },
    })

    assert provider.name == "akshare"
    assert provider.timeout_seconds == 23


def test_pipeline_uses_explicit_provider_when_config_is_invalid(tmp_path: Path, monkeypatch):
    repository = QuantRepository(tmp_path / "quant.duckdb")

    def fail_create_provider(config):
        raise AssertionError("create_provider should not be called")

    monkeypatch.setattr("quant.services.pipeline.create_provider", fail_create_provider)

    pipeline = QuantPipeline(repository=repository, provider=MockProvider())

    assert isinstance(pipeline.provider, MockProvider)


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


def test_pipeline_daily_sync_reuses_today_snapshot(tmp_path: Path):
    db_path = tmp_path / "quant.duckdb"
    repository = QuantRepository(db_path)
    provider = CountingMockProvider()
    pipeline = QuantPipeline(repository=repository, provider=provider)

    first_result = pipeline.sync_data_daily(
        "2024-01-02",
        "2024-03-31",
        ["CSI300"],
        sync_date="2026-05-27",
    )
    second_result = pipeline.sync_data_daily(
        "2024-01-02",
        "2024-03-31",
        ["CSI300"],
        sync_date="2026-05-27",
    )

    assert first_result["cache_hit"] is False
    assert first_result["status"] == "synced"
    assert second_result["cache_hit"] is True
    assert second_result["status"] == "cached"
    assert second_result["stock_count"] == 6
    assert second_result["daily_bar_count"] == first_result["daily_bar_count"]
    assert provider.stock_basic_calls == 1


def test_pipeline_fast_daily_sync_writes_stock_pool_before_market_data(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    provider = CountingMockProvider()
    pipeline = QuantPipeline(repository=repository, provider=provider)
    repository.replace_table("daily_bar", MockProvider().get_daily_bars("2024-01-02", "2024-03-31"))
    repository.replace_table("valuation", MockProvider().get_valuation("2024-01-02", "2024-03-31"))

    result = pipeline.sync_data_daily_fast(
        "2024-01-02",
        "2024-03-31",
        ["CSI300"],
        sync_date="2026-05-27",
    )

    assert result["status"] == "stock_pool_synced"
    assert result["cache_hit"] is False
    assert result["stock_count"] == 6
    assert result["index_member_count"] == 6
    assert result["daily_bar_count"] == 0
    assert repository.count_rows("stock_basic") == 6
    assert repository.count_rows("index_member") == 6
    assert repository.count_rows("daily_bar") == 0
    assert provider.stock_basic_calls == 1
    assert provider.daily_bar_calls == 0
    assert provider.valuation_calls == 0


def test_pipeline_market_data_batch_sync_limits_codes(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    provider = CountingMockProvider()
    pipeline = QuantPipeline(repository=repository, provider=provider)
    pipeline.sync_data_daily_fast("2024-01-02", "2024-03-31", ["CSI300"], sync_date="2026-05-27")

    result = pipeline.sync_market_data_batch("2024-01-02", "2024-03-31", batch_size=2)

    assert result["status"] == "market_batch_synced"
    assert result["batch_size"] == 2
    assert result["processed_count"] == 2
    assert result["remaining_count"] == 4
    assert result["daily_bar_count"] > 0
    assert repository.count_rows("daily_bar") == result["daily_bar_count"]
    assert provider.daily_bar_calls == 1
    assert provider.valuation_calls == 1


def test_pipeline_daily_snapshot_reports_partial_market_data(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())
    pipeline.sync_data_daily_fast("2024-01-02", "2024-03-31", ["CSI300"], sync_date="2026-05-27")

    snapshot = pipeline.daily_sync_snapshot(sync_date="2026-05-27")

    assert snapshot["status"] == "stock_pool_synced"
    assert snapshot["cache_hit"] is True
    assert snapshot["stock_count"] == 6
    assert snapshot["market_synced_count"] == 0
    assert snapshot["market_remaining_count"] == 6


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
