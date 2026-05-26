from pathlib import Path

from quant.calendar.service import TradingCalendarService
from quant.providers.mock_provider import MockProvider
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_repository(tmp_path: Path) -> QuantRepository:
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    return repository


def test_calendar_returns_next_trade_day_and_month_ends(tmp_path):
    repository = build_repository(tmp_path)
    service = TradingCalendarService(repository)

    assert service.next_trade_date("2024-01-31") == "2024-02-01"
    assert "2024-01-31" in service.month_end_trade_dates("2024-01-02", "2024-03-31")
    assert "2024-02-29" in service.month_end_trade_dates("2024-01-02", "2024-03-31")


def test_universe_builds_filtered_index_pool(tmp_path):
    repository = build_repository(tmp_path)
    service = UniverseService(repository)

    universe = service.build_universe(
        trade_date="2024-01-31",
        index_codes=["CSI300"],
        min_listed_days=120,
        min_avg_amount_20d=50000000,
        include_st=False,
        exclude_suspended=True,
    )

    assert len(universe) == 6
    assert universe[0]["code"] == "600001"
    assert all(item["avg_amount_20d"] >= 50000000 for item in universe)
