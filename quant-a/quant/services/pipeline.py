from pathlib import Path
from typing import Dict, List, Optional

from quant.backtest.service import BacktestService
from quant.calendar.service import TradingCalendarService
from quant.factors.engine import FactorEngine
from quant.portfolio.service import PortfolioService
from quant.providers.mock_provider import MockProvider
from quant.reports.service import ReportService
from quant.risk.service import RiskService
from quant.scoring.service import ScoringService
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


class QuantPipeline:
    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[MockProvider] = None):
        self.repository = repository or QuantRepository(Path("data/quant.duckdb"))
        self.provider = provider or MockProvider()

    def sync_data(self, start_date: str, end_date: str, index_codes: List[str]) -> Dict[str, object]:
        calendar = self.provider.get_trade_calendar(start_date, end_date)
        stocks = self.provider.get_stock_basic()
        daily_bars = self.provider.get_daily_bars(start_date, end_date)
        valuations = self.provider.get_valuation(start_date, end_date)
        financials = self.provider.get_financials()
        members = self.provider.get_index_members(index_codes, end_date)
        data_version = self.provider.data_version

        counts = {
            "calendar_count": self.repository.replace_table("trade_calendar", calendar),
            "stock_count": self.repository.replace_table("stock_basic", stocks),
            "daily_bar_count": self.repository.replace_table("daily_bar", daily_bars),
            "valuation_count": self.repository.replace_table("valuation", valuations),
            "financial_count": self.repository.replace_table("financial", financials),
            "index_member_count": self.repository.replace_table("index_member", members),
        }
        self.repository.record_data_version(data_version, "mock", start_date, end_date)
        return {
            "data_version": data_version,
            **counts,
        }

    def run_scores(self, trade_date: str, index_codes: List[str]) -> Dict[str, object]:
        universe = UniverseService(self.repository).build_universe(trade_date, index_codes, 120, 50000000, False, True)
        factors = FactorEngine(self.repository).calculate(trade_date, universe)
        scores = ScoringService().score(trade_date, factors, self.repository.latest_data_version(), "v0.1")
        return {
            "trade_date": trade_date,
            "scores": scores,
        }

    def run_backtest(self, start_date: str, end_date: str, index_codes: List[str], initial_cash: float) -> Dict[str, object]:
        calendar = TradingCalendarService(self.repository)
        score_dates = calendar.month_end_trade_dates(start_date, end_date)
        scores_by_date = {}
        skipped_score_dates = []
        for trade_date in score_dates:
            try:
                scores_by_date[trade_date] = self.run_scores(trade_date, index_codes)["scores"]
            except ValueError as exc:
                skipped_score_dates.append({
                    "trade_date": trade_date,
                    "reason": str(exc),
                })

        backtest = BacktestService(self.repository, calendar, PortfolioService(top_n=3, single_stock_weight_limit=0.05))
        result = backtest.run(start_date, end_date, scores_by_date, initial_cash)
        report = ReportService(RiskService()).build_report(result["experiment_id"], result)
        return {
            "backtest": result,
            "report": report,
            "skipped_score_dates": skipped_score_dates,
        }
