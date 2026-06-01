from pathlib import Path

import pytest

from quant.backtest.service import BacktestService
from quant.calendar.service import TradingCalendarService
from quant.factors.engine import FactorEngine
from quant.portfolio.service import PortfolioService
from quant.providers.mock_provider import MockProvider
from quant.reports.service import ReportService
from quant.risk.service import RiskService
from quant.scoring.service import ScoringService
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_scores(repository: QuantRepository, trade_date: str):
    universe = UniverseService(repository).build_universe(trade_date, ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate(trade_date, universe)
    return ScoringService().score(trade_date, factors, repository.latest_data_version(), "v0.1")


def build_backtest(tmp_path: Path, top_n: int = 3, single_stock_weight_limit: float = 0.05):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    calendar = TradingCalendarService(repository)
    portfolio = PortfolioService(top_n=top_n, single_stock_weight_limit=single_stock_weight_limit)
    backtest = BacktestService(repository, calendar, portfolio)
    return repository, backtest


def test_monthly_backtest_outputs_report(tmp_path: Path):
    repository, backtest = build_backtest(tmp_path)
    scores_by_date = {
        "2024-01-31": build_scores(repository, "2024-01-31"),
        "2024-02-29": build_scores(repository, "2024-02-29"),
    }

    result = backtest.run("2024-01-02", "2024-03-31", scores_by_date, initial_cash=1000000.0)
    report = ReportService(RiskService()).build_report("exp-test", result)

    assert result["experiment_id"].startswith("bt-")
    assert len(result["nav"]) > 0
    assert len(result["orders"]) > 0
    assert report["experiment_id"] == "exp-test"
    assert "known_biases" in report
    assert report["metrics"]["max_drawdown"] <= 0


def test_nav_before_first_execution_date_has_no_future_holdings(tmp_path: Path):
    repository, backtest = build_backtest(tmp_path)
    scores_by_date = {
        "2024-01-31": build_scores(repository, "2024-01-31"),
    }

    result = backtest.run("2024-01-02", "2024-03-31", scores_by_date, initial_cash=1000000.0)

    before_execution = [item for item in result["nav"] if item["trade_date"] <= "2024-01-31"]
    assert len(before_execution) > 0
    assert all(item["market_value"] == 0 for item in before_execution)
    assert all(item["total_asset"] == 1000000.0 for item in before_execution)
    assert all(item["nav"] == 1.0 for item in before_execution)


def test_repeated_rebalance_trades_delta_instead_of_accumulating_full_target(tmp_path: Path):
    repository, backtest = build_backtest(tmp_path, top_n=1, single_stock_weight_limit=0.05)
    first_scores = build_scores(repository, "2024-01-31")
    second_scores = build_scores(repository, "2024-02-29")
    target_code = str(first_scores[0]["code"])
    assert target_code == str(second_scores[0]["code"])

    result = backtest.run(
        "2024-01-02",
        "2024-03-31",
        {
            "2024-01-31": first_scores,
            "2024-02-29": second_scores,
        },
        initial_cash=1000000.0,
    )

    buy_orders = [
        order for order in result["orders"]
        if order["code"] == target_code and order["side"] == "buy" and order["order_status"] == "filled"
    ]
    assert len(buy_orders) >= 1
    assert sum(float(order["filled_quantity"]) for order in buy_orders) < float(buy_orders[0]["filled_quantity"]) * 1.5


def test_missing_close_price_raises_clear_error(tmp_path: Path):
    repository, backtest = build_backtest(tmp_path)

    with pytest.raises(ValueError, match="Missing close price for 600001 on 2099-01-01"):
        backtest._close_price("2099-01-01", "600001")
