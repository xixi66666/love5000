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
            "daily_bar_count": self.repository.count_rows("daily_bar"),
            "valuation_count": self.repository.count_rows("valuation"),
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

    def sync_market_data_batch(self, start_date: str, end_date: str, batch_size: int = 10) -> Dict[str, object]:
        pending_codes = self._pending_market_data_codes()
        batch_codes = pending_codes[:batch_size]
        daily_bars = self.provider.get_daily_bars(start_date, end_date, codes=batch_codes)
        valuations = self._valuations_from_daily_bars(start_date, end_date, batch_codes, daily_bars)

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

    def _valuations_from_daily_bars(
        self,
        start_date: str,
        end_date: str,
        batch_codes: List[str],
        daily_bars: List[object],
    ) -> List[object]:
        derive = getattr(self.provider, "derive_valuation_from_daily_bars", None)
        if callable(derive):
            return derive(daily_bars)
        return self.provider.get_valuation(start_date, end_date, codes=batch_codes)

    def daily_sync_snapshot(self, sync_date: Optional[str] = None) -> Optional[Dict[str, object]]:
        today = sync_date or date.today().isoformat()
        cached_snapshot = self.repository.latest_data_snapshot_for_day(self.provider_name, today)
        if not cached_snapshot:
            return None
        total_stocks = self.repository.count_rows("stock_basic")
        market_synced_count = self._market_synced_count()
        valuation_synced_count = self._valuation_synced_count()
        status = "cached" if (
            total_stocks > 0
            and market_synced_count >= total_stocks
            and valuation_synced_count >= total_stocks
        ) else "stock_pool_synced"
        result = self._daily_sync_result(status, True, cached_snapshot)
        result["market_synced_count"] = market_synced_count
        result["market_remaining_count"] = max(0, total_stocks - market_synced_count)
        result["valuation_synced_count"] = valuation_synced_count
        result["valuation_remaining_count"] = max(0, total_stocks - valuation_synced_count)
        return result

    def data_integrity(self) -> Dict[str, object]:
        stock_count = self.repository.count_rows("stock_basic")
        daily_bar_count = self.repository.count_rows("daily_bar")
        valuation_count = self.repository.count_rows("valuation")
        financial_count = self.repository.count_rows("financial")
        index_member_count = self.repository.count_rows("index_member")
        market_synced_count = self._market_synced_count()
        valuation_synced_count = self._valuation_synced_count()
        latest_score_date = self._latest_score_date()
        score_ready_stock_count = self._score_ready_stock_count(latest_score_date) if latest_score_date else 0
        blocking_reasons = self._score_blocking_reasons(
            stock_count,
            daily_bar_count,
            valuation_count,
            financial_count,
            score_ready_stock_count,
        )

        return {
            "stock_count": stock_count,
            "daily_bar_count": daily_bar_count,
            "valuation_count": valuation_count,
            "financial_count": financial_count,
            "index_member_count": index_member_count,
            "market_synced_count": market_synced_count,
            "market_remaining_count": max(0, stock_count - market_synced_count),
            "valuation_synced_count": valuation_synced_count,
            "valuation_remaining_count": max(0, stock_count - valuation_synced_count),
            "latest_score_date": latest_score_date,
            "score_ready": latest_score_date is not None and score_ready_stock_count > 0 and not blocking_reasons,
            "score_ready_stock_count": score_ready_stock_count,
            "blocking_reasons": blocking_reasons,
        }

    def run_scores(self, trade_date: str, index_codes: List[str]) -> Dict[str, object]:
        self._ensure_score_inputs_ready(trade_date)
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
            left join (
                select distinct code from valuation
            ) v on s.code = v.code
            where d.code is null or v.code is null
            order by s.exchange, s.code
        """)
        return [str(row["code"]) for row in rows]

    def _market_synced_count(self) -> int:
        row = self.repository.fetch_dicts("select count(distinct code) as count from daily_bar")
        return int(row[0]["count"]) if row else 0

    def _valuation_synced_count(self) -> int:
        row = self.repository.fetch_dicts("select count(distinct code) as count from valuation")
        return int(row[0]["count"]) if row else 0

    def _latest_score_date(self) -> Optional[str]:
        rows = self.repository.fetch_dicts("""
            with daily_dates as (
                select trade_date
                from daily_bar
                group by trade_date
            ),
            valuation_dates as (
                select trade_date
                from valuation
                group by trade_date
            )
            select d.trade_date
            from daily_dates d
            join valuation_dates v on d.trade_date = v.trade_date
            order by d.trade_date desc
            limit 1
        """)
        return str(rows[0]["trade_date"]) if rows else None

    def _score_ready_stock_count(self, trade_date: str) -> int:
        rows = self.repository.fetch_dicts("""
            with daily_codes as (
                select distinct code
                from daily_bar
                where trade_date <= ? and available_date <= ?
            ),
            valuation_codes as (
                select distinct code
                from valuation
                where trade_date <= ? and available_date <= ?
            ),
            financial_codes as (
                select distinct code
                from financial
                where available_date <= ?
            )
            select count(distinct s.code) as count
            from stock_basic s
            join daily_codes d on s.code = d.code
            join valuation_codes v on s.code = v.code
            join financial_codes f on s.code = f.code
            where s.status = 'listed'
        """, [trade_date, trade_date, trade_date, trade_date, trade_date])
        return int(rows[0]["count"]) if rows else 0

    def _score_blocking_reasons(
        self,
        stock_count: int,
        daily_bar_count: int,
        valuation_count: int,
        financial_count: int,
        score_ready_stock_count: int,
    ) -> List[str]:
        reasons = []
        if stock_count == 0:
            reasons.append("股票基础数据为空")
        if daily_bar_count == 0:
            reasons.append("行情数据为空")
        if valuation_count == 0:
            reasons.append("估值数据为空")
        if financial_count == 0:
            reasons.append("财务数据为空")
        if stock_count > 0 and daily_bar_count > 0 and valuation_count > 0 and financial_count > 0 and score_ready_stock_count == 0:
            reasons.append("没有同时具备行情、估值和财务数据的可评分股票")
        return reasons

    def _ensure_score_inputs_ready(self, trade_date: str) -> None:
        integrity = self.data_integrity()
        score_ready_stock_count = self._score_ready_stock_count(trade_date)
        blocking_reasons = self._score_blocking_reasons(
            int(integrity["stock_count"]),
            int(integrity["daily_bar_count"]),
            int(integrity["valuation_count"]),
            int(integrity["financial_count"]),
            score_ready_stock_count,
        )
        if blocking_reasons:
            raise ValueError("本地数据不足，无法评分：" + "；".join(blocking_reasons))

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
