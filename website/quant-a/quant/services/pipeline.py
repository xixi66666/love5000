"""量化流水线的编排层 `QuantPipeline`。

把 Provider、DuckDB 仓储与各领域服务串成三条主流程：

- 数据同步：全量 `sync_data`、当日增量 `sync_data_daily` / `sync_data_daily_fast`，
  以及按批补行情的 `sync_market_data_batch`；
- 研究：`run_scores` 依次执行"选股池 → 因子 → 评分"；
- 回测：`run_backtest` 用月末信号在下一交易日调仓，再组装报告。

配置全部来自 `configs/*.yaml`（Provider、DuckDB 路径、选股过滤、模型参数）。
构造函数支持注入 repository/provider，测试因此能在临时目录用 `MockProvider`
跑通全流程而不联网。写操作为整表替换或"按代码删除后重插"；评分前先做数据完整性
检查，不足时抛 `ValueError`，由 API 层转成 400 与中文原因。所有输出只用于研究，
不构成投资建议。
"""

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
    """串起 Provider、仓储与因子/评分/回测服务的编排器。"""

    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[DataProvider] = None):
        """按配置构造仓储与数据源。

        Args:
            repository: 可选的本地仓储；为空时按 `app.yaml` 的
                `storage.duckdb_path` 打开（相对路径以进程工作目录为基准）。
            provider: 可选数据源；为空时按 `provider.active` 走 `create_provider`。
                显式传入时不会调用工厂，因此配置文件里的 Provider 名称不影响本次运行。

        Raises:
            KeyError: `app.yaml` 缺少 `storage.duckdb_path`。
            ValueError: 配置的 `provider.active` 不受支持（此时 `provider` 未显式传入）。
        """
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
        """全量同步：拉取六类数据并整表替换。

        `replace_table` 是"先清空再插入"的事务操作，单表失败会回滚该表，但此前已提交
        的表保持新数据；因此一次失败的全量同步可能留下部分更新的本地库。

        Args:
            start_date: 区间起（含）。
            end_date: 区间止（含），同时作为指数成分的查询日。
            index_codes: 指数代码，或 `FULL_MARKET`/`ALL`。
            sync_date: 写入 `data_versions.created_at` 的日期；为空时用数据库默认时间。

        Returns:
            含 `data_version` 与各表写入行数（`calendar_count`、`stock_count`、
            `daily_bar_count`、`valuation_count`、`financial_count`、
            `index_member_count`）的字典。

        Raises:
            Exception: Provider 的上游异常原样抛出；仓储列校验失败抛 `ValueError`。
        """
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
        """当日增量同步：当天已有快照就直接复用，否则执行一次全量同步。

        Args:
            start_date: 区间起（含）。
            end_date: 区间止（含）。
            index_codes: 指数代码，或 `FULL_MARKET`/`ALL`。
            sync_date: 覆盖"今天"的日期，仅用于测试或补数。

        Returns:
            命中快照时 `status=cached`、`cache_hit=True` 并附带各表计数；否则
            `status=synced`、`cache_hit=False`，其余字段与 `sync_data` 相同。
        """
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
        """只同步"股票池"部分的快速增量。

        只写日历、股票基础、财务与指数成分，行情和估值留给
        `sync_market_data_batch` 分批补齐，避免单次请求卡在全市场行情上。返回的
        `daily_bar_count`/`valuation_count` 是表里已有的行数，不是本次写入数。

        Args:
            start_date: 区间起（含）。
            end_date: 区间止（含）。
            index_codes: 指数代码，或 `FULL_MARKET`/`ALL`。
            sync_date: 覆盖"今天"的日期。
            force: 为真时忽略当天快照强制重跑。

        Returns:
            `status=stock_pool_synced`、`cache_hit=False`、`data_version` 与各表计数；
            命中快照且未强制时返回 `status=cached`、`cache_hit=True`。
        """
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
        """为"缺行情或缺估值"的股票补一批数据。

        待补代码由 `_pending_market_data_codes` 决定；每次最多处理 `batch_size` 只，
        先按代码删除旧行再追加，保证重复执行幂等（不会产生重复行）。

        Args:
            start_date: 行情区间起（含）。
            end_date: 行情区间止（含）。
            batch_size: 单批股票数，默认 10。

        Returns:
            `batch_size`、`processed_count`、`remaining_count`（补完后仍待处理的股票数，
            为 0 时调用方可以结束循环）以及本次写入的 `daily_bar_count`、
            `valuation_count`。

        Raises:
            Exception: Provider 或仓储异常原样抛出，已提交的批次不回滚。
        """
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
        """生成与本批行情配套的估值行。

        优先调用 Provider 的 `derive_valuation_from_daily_bars`（Mock/AkShare 均实现），
        一次行情请求即可同时得到估值；没有该能力的 Provider 回退到
        `get_valuation(..., codes=batch_codes)`，此时会多一次外部请求。

        Args:
            start_date: 估值区间起（含），仅回退路径使用。
            end_date: 估值区间止（含），仅回退路径使用。
            batch_codes: 本批股票代码，仅回退路径使用。
            daily_bars: 本批已抓到的行情行。

        Returns:
            估值行列表，长度通常与 `daily_bars` 相同。
        """
        derive = getattr(self.provider, "derive_valuation_from_daily_bars", None)
        if callable(derive):
            return derive(daily_bars)
        return self.provider.get_valuation(start_date, end_date, codes=batch_codes)

    def daily_sync_snapshot(self, sync_date: Optional[str] = None) -> Optional[Dict[str, object]]:
        """读取当天快照，并补充行情/估值的补齐进度。

        Args:
            sync_date: 覆盖"今天"的日期，仅用于测试。

        Returns:
            `None` 表示当天没有快照；否则返回字典：`status` 为 `cached`（行情与估值
            都覆盖了全部在市股票）或 `stock_pool_synced`（只完成股票池），另含
            `market_synced_count`、`market_remaining_count`、
            `valuation_synced_count`、`valuation_remaining_count` 与各表计数。
        """
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
        """汇总本地数据完整性与可评分状态（只读）。

        Returns:
            各表行数、行情/估值已覆盖的股票数与剩余数、`latest_score_date`（行情与估值
            都有数据的最近交易日）、`score_ready`（存在可评分日、有可评分股票且没有
            阻断原因）、`score_ready_stock_count`，以及中文 `blocking_reasons`。
            页面据此提示"先同步数据再评分"。
        """
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
        """运行一次完整评分。

        流程：先检查本地数据是否足够，再按 `universe.yaml` 的过滤条件构造股票池，
        计算因子，最后合成总分、排名并写入当前数据版本与模型版本。

        Args:
            trade_date: 评分交易日（ISO 日期）。
            index_codes: 指数代码，或 `FULL_MARKET`/`ALL`。

        Returns:
            `{trade_date, scores}`；`scores` 按总分降序，含维度分、排名、缺失字段与
            风险标记。分数只用于研究排序，不构成买入建议。

        Raises:
            ValueError: 本地缺行情/估值/财务（消息为中文，API 层转 400）；因子输入
                缺失或非法（如 `pb=0`）时同样抛 `ValueError`。
        """
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
        """运行月末调仓回测并生成报告。

        先取区间内所有月末交易日逐个评分；某日数据不足时记入 `skipped_score_dates`
        并继续，而不是用空股票池"假调仓"。随后 `BacktestService` 在信号日的下一个
        交易日成交，`ReportService` 汇总净值、最大回撤与偏差披露。

        Args:
            start_date: 回测区间起（含）。
            end_date: 回测区间止（含）；区间外价格不参与计算。
            index_codes: 选股池指数代码，或 `FULL_MARKET`/`ALL`。
            initial_cash: 初始资金，单位人民币元。

        Returns:
            `{backtest, report, skipped_score_dates}`；`backtest` 含 `nav`/`orders`/
            `holdings`，`report` 含指标与 `known_biases`（非投资建议边界）。

        Raises:
            Exception: 缺少成交价（`Missing open/close price`）等错误不捕获，
                直接冒泡给 API 层；只有评分阶段的 `ValueError` 会被跳过。
        """
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
        """推断 Provider 名称，用于 `data_versions.provider` 与当天快照匹配。

        优先用实例的 `name` 属性；没有时用类名去掉 `Provider` 后缀再转小写，
        使 `TushareProvider` 得到 `tushare`，自定义实现也能得到稳定标识。
        """
        name = getattr(provider, "name", None)
        if name:
            return name
        class_name = provider.__class__.__name__
        if class_name.endswith("Provider"):
            class_name = class_name[:-len("Provider")]
        return class_name.lower()

    def _pending_market_data_codes(self) -> List[str]:
        """列出缺行情或缺估值的股票代码。

        以 `stock_basic` 左连接两张表的去重代码集，任一侧为空即视为待补；按交易所与
        代码排序，保证分批顺序稳定、分批结果可复现。
        """
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
        """统计已有行情的股票数（`daily_bar` 去重代码）。"""
        row = self.repository.fetch_dicts("select count(distinct code) as count from daily_bar")
        return int(row[0]["count"]) if row else 0

    def _valuation_synced_count(self) -> int:
        """统计已有估值的股票数（`valuation` 去重代码）。"""
        row = self.repository.fetch_dicts("select count(distinct code) as count from valuation")
        return int(row[0]["count"]) if row else 0

    def _latest_score_date(self) -> Optional[str]:
        """取行情与估值都存在的最近交易日。

        两边日期取交集后倒序取第一条，用作"最近可评分日期"；没有交集返回 `None`，
        页面据此提示尚未同步或数据不完整。
        """
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
        """统计某日同时具备行情、估值与财务的在市股票数。

        三个 CTE 都按 `available_date <= 决策日` 过滤，避免把尚未公布的财报或当天
        收盘后才有的数据算进可评分集合。

        Args:
            trade_date: 决策日，ISO 日期。

        Returns:
            同时满足三张表的在市股票数；无数据时为 0。
        """
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
        """把数据缺失情况翻译成可直接展示的中文阻断原因。

        Args:
            stock_count: `stock_basic` 行数。
            daily_bar_count: `daily_bar` 行数。
            valuation_count: `valuation` 行数。
            financial_count: `financial` 行数。
            score_ready_stock_count: 目标交易日可评分的股票数。

        Returns:
            原因列表；为空表示数据足够评分。四类数据都不为空但没有交集时，会额外
            给出一条更具体的"没有同时具备行情、估值和财务数据的可评分股票"。
        """
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
        """评分前的数据闸门。

        Args:
            trade_date: 即将评分的交易日。

        Raises:
            ValueError: 存在任一阻断原因；消息以"本地数据不足，无法评分："开头，
                API 层原样放进 HTTP 400 的 `message`。
        """
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
        """把 `data_versions` 快照行展开成接口响应。

        Args:
            status: `cached` 或 `stock_pool_synced`。
            cache_hit: 是否命中当天快照。
            snapshot: `data_versions` 行，可能缺少部分键。

        Returns:
            含状态、数据版本、Provider、同步区间与各表当前行数的字典；缺失键以空串
            兜底，避免前端拿不到字段。
        """
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
