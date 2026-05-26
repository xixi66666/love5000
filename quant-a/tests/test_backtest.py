from pathlib import Path

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


def test_monthly_backtest_outputs_report(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    calendar = TradingCalendarService(repository)
    portfolio = PortfolioService(top_n=3, single_stock_weight_limit=0.05)
    backtest = BacktestService(repository, calendar, portfolio)
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
