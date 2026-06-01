from pathlib import Path
from datetime import date
from typing import Dict, List, Optional

from quant.backtest.service import BacktestService
from quant.calendar.service import TradingCalendarService
from quant.common.config import load_app_config, load_model_config, load_universe_config
from quant.factors.engine import FactorEngine
from quant.portfolio.service import PortfolioService
from quant.providers.base import DataProvider
from quant.providers.factory import create_provider
from quant.reports.service import ReportService
from quant.risk.service import RiskService
from quant.scoring.service import ScoringService
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


class QuantPipeline:
    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[DataProvider] = None):
        app_config = load_app_config()
        duckdb_path = app_config["storage"]["duckdb_path"]
        self.repository = repository or QuantRepository(Path(duckdb_path))
        self.provider = provider or create_provider(app_config)
        self.provider_name = self._provider_name(self.provider)

    def sync_data(
        self,
        start_date: str,
        end_date: str,
        index_codes: List[str],
        sync_date: Optional[str] = None,
    ) -> Dict[str, object]:
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
        self.repository.record_data_version(data_version, self.provider_name, start_date, end_date, sync_date)
        return {
            "data_version": data_version,
            **counts,
        }

    def sync_data_daily(
        self,
        start_date: str,
        end_date: str,
        index_codes: List[str],
        sync_date: Optional[str] = None,
    ) -> Dict[str, object]:
        today = sync_date or date.today().isoformat()
        cached_snapshot = self.repository.latest_data_snapshot_for_day(self.provider_name, today)
        if cached_snapshot:
            return self._daily_sync_result("cached", True, cached_snapshot)

        result = self.sync_data(start_date, end_date, index_codes, sync_date=today)
        return {
            "status": "synced",
            "cache_hit": False,
            **result,
        }

    def sync_data_daily_fast(
        self,
        start_date: str,
        end_date: str,
        index_codes: List[str],
        sync_date: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, object]:
        today = sync_date or date.today().isoformat()
        cached_snapshot = self.repository.latest_data_snapshot_for_day(self.provider_name, today)
        if cached_snapshot and not force:
            return self._daily_sync_result("cached", True, cached_snapshot)

        calendar = self.provider.get_trade_calendar(start_date, end_date)
        stocks = self.provider.get_stock_basic()
        financials = self.provider.get_financials()
        members = self.provider.get_index_members(index_codes, end_date)
        data_version = self.provider.data_version

        counts = {
            "calendar_count": self.repository.replace_table("trade_calendar", calendar),
            "stock_count": self.repository.replace_table("stock_basic", stocks),
            "daily_bar_count": self.repository.replace_table("daily_bar", []),
            "valuation_count": self.repository.replace_table("valuation", []),
            "financial_count": self.repository.replace_table("financial", financials),
            "index_member_count": self.repository.replace_table("index_member", members),
        }
        self.repository.record_data_version(data_version, self.provider_name, start_date, end_date, today)
        return {
            "status": "stock_pool_synced",
            "cache_hit": False,
            "data_version": data_version,
            **counts,
        }

    def sync_market_data_batch(self, start_date: str, end_date: str, batch_size: int = 100) -> Dict[str, object]:
        pending_codes = self._pending_market_data_codes()
        batch_codes = pending_codes[:batch_size]
        daily_bars = self.provider.get_daily_bars(start_date, end_date, codes=batch_codes)
        valuations = self.provider.get_valuation(start_date, end_date, codes=batch_codes)

        self.repository.delete_rows_for_codes("daily_bar", "code", batch_codes)
        self.repository.delete_rows_for_codes("valuation", "code", batch_codes)
        daily_bar_count = self.repository.append_rows("daily_bar", daily_bars)
        valuation_count = self.repository.append_rows("valuation", valuations)

        return {
            "status": "market_batch_synced",
            "batch_size": batch_size,
            "processed_count": len(batch_codes),
            "remaining_count": max(0, len(pending_codes) - len(batch_codes)),
            "daily_bar_count": daily_bar_count,
            "valuation_count": valuation_count,
        }

    def daily_sync_snapshot(self, sync_date: Optional[str] = None) -> Optional[Dict[str, object]]:
        today = sync_date or date.today().isoformat()
        cached_snapshot = self.repository.latest_data_snapshot_for_day(self.provider_name, today)
        if not cached_snapshot:
            return None
        total_stocks = self.repository.count_rows("stock_basic")
        market_synced_count = self._market_synced_count()
        status = "cached" if total_stocks > 0 and market_synced_count >= total_stocks else "stock_pool_synced"
        result = self._daily_sync_result(status, True, cached_snapshot)
        result["market_synced_count"] = market_synced_count
        result["market_remaining_count"] = max(0, total_stocks - market_synced_count)
        return result

    def run_scores(self, trade_date: str, index_codes: List[str]) -> Dict[str, object]:
        universe_filters = load_universe_config()["universe"]["filters"]
        model_config = load_model_config()["model"]
        universe = UniverseService(self.repository).build_universe(
            trade_date,
            index_codes,
            universe_filters["min_listed_days"],
            universe_filters["min_avg_amount_20d"],
            universe_filters["include_st"],
            universe_filters["exclude_suspended"],
        )
        factors = FactorEngine(self.repository).calculate(trade_date, universe)
        scores = ScoringService().score(
            trade_date,
            factors,
            self.repository.latest_data_version(),
            model_config["version"],
        )
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

        model_config = load_model_config()["model"]
        backtest = BacktestService(
            self.repository,
            calendar,
            PortfolioService(
                top_n=model_config["top_n"],
                single_stock_weight_limit=model_config["single_stock_weight_limit"],
            ),
        )
        result = backtest.run(start_date, end_date, scores_by_date, initial_cash)
        report = ReportService(RiskService()).build_report(result["experiment_id"], result)
        return {
            "backtest": result,
            "report": report,
            "skipped_score_dates": skipped_score_dates,
        }

    def _provider_name(self, provider: DataProvider) -> str:
        name = getattr(provider, "name", None)
        if name:
            return name
        class_name = provider.__class__.__name__
        if class_name.endswith("Provider"):
            class_name = class_name[:-len("Provider")]
        return class_name.lower()

    def _pending_market_data_codes(self) -> List[str]:
        rows = self.repository.fetch_dicts("""
            select s.code
            from stock_basic s
            left join (
                select distinct code from daily_bar
            ) d on s.code = d.code
            where d.code is null
            order by s.exchange, s.code
        """)
        return [str(row["code"]) for row in rows]

    def _market_synced_count(self) -> int:
        row = self.repository.fetch_dicts("select count(distinct code) as count from daily_bar")
        return int(row[0]["count"]) if row else 0

    def _daily_sync_result(self, status: str, cache_hit: bool, snapshot: Dict[str, object]) -> Dict[str, object]:
        return {
            "status": status,
            "cache_hit": cache_hit,
            "data_version": snapshot.get("data_version", ""),
            "provider": snapshot.get("provider", ""),
            "start_date": snapshot.get("start_date", ""),
            "end_date": snapshot.get("end_date", ""),
            "stock_count": self.repository.count_rows("stock_basic"),
            "daily_bar_count": self.repository.count_rows("daily_bar"),
            "valuation_count": self.repository.count_rows("valuation"),
            "financial_count": self.repository.count_rows("financial"),
            "index_member_count": self.repository.count_rows("index_member"),
        }
