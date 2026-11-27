"""`BacktestService` 的执行时序与未来数据隔离测试。

覆盖分支：月末信号在次日成交并生成报告与最大回撤；首次执行日前净值恒为 1.0、
没有未来持仓；重复调仓只交易差额而不是累加满仓；缺失收盘价时抛出可读 `ValueError`；
`end_date` 之后的行情被篡改也不影响结果（价格前视防护）；月末信号执行日超出回测
窗口时被丢弃；窗口最后一天仍需成交时不需要窗口外的价格行。

隔离方式：每个用例在临时目录建 DuckDB，用 `MockProvider` 写入固定行情，
直接构造评分或用固定分数构造信号；不访问真实行情、不启动服务。
"""

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


def build_backtest(
    tmp_path: Path,
    top_n: int = 3,
    single_stock_weight_limit: float = 0.05,
    data_end_date: str = "2024-03-31",
):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data(
        "2024-01-02", data_end_date, ["CSI300"]
    )
    calendar = TradingCalendarService(repository)
    portfolio = PortfolioService(top_n=top_n, single_stock_weight_limit=single_stock_weight_limit)
    backtest = BacktestService(repository, calendar, portfolio)
    return repository, backtest


def fixed_scores(*codes: str):
    return [
        {
            "code": code,
            "name": code,
            "industry": "测试",
            "rank": rank,
            "total_score": 100.0 - rank,
        }
        for rank, code in enumerate(codes, start=1)
    ]


def mutate_prices_after(repository: QuantRepository, end_date: str) -> int:
    rows = repository.fetch_dicts(
        "select count(*) as count from daily_bar where trade_date > ?",
        [end_date],
    )
    count = int(rows[0]["count"])
    repository.connection.execute(
        """
        update daily_bar
        set open = open * 1000.0,
            high = high * 1000.0,
            low = low * 1000.0,
            close = close * 1000.0,
            pre_close = pre_close * 1000.0
        where trade_date > ?
        """,
        [end_date],
    )
    return count


def assert_same_backtest_result(left, right) -> None:
    assert left["initial_cash"] == right["initial_cash"]
    assert left["nav"] == right["nav"]
    assert left["orders"] == right["orders"]
    assert left["holdings"] == right["holdings"]


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


def test_prices_after_end_date_do_not_change_backtest_result(tmp_path: Path):
    repository, backtest = build_backtest(
        tmp_path,
        top_n=2,
        single_stock_weight_limit=0.2,
        data_end_date="2024-04-30",
    )
    scores_by_date = {
        "2024-01-31": fixed_scores("600001", "600002"),
        "2024-02-29": fixed_scores("600001", "600002"),
        "2024-03-29": fixed_scores("600002", "600003"),
    }
    end_date = "2024-04-01"
    baseline = backtest.run("2024-01-02", end_date, scores_by_date, initial_cash=1000000.0)

    end_date_orders = [
        order for order in baseline["orders"]
        if order["signal_date"] == "2024-03-29"
    ]
    assert end_date_orders
    assert {order["trade_date"] for order in end_date_orders} == {end_date}
    assert {order["side"] for order in end_date_orders} == {"buy", "sell"}
    assert all(order["signal_date"] < order["trade_date"] for order in baseline["orders"])
    assert all(order["trade_date"] <= end_date for order in baseline["orders"])
    assert len({order["order_id"] for order in baseline["orders"]}) == len(baseline["orders"])
    assert baseline["nav"][-1]["trade_date"] == end_date

    final_nav = baseline["nav"][-1]
    expected_market_value = 0.0
    for code, quantity in baseline["holdings"].items():
        close_rows = repository.fetch_dicts(
            "select close from daily_bar where trade_date = ? and code = ?",
            [end_date, code],
        )
        expected_market_value += float(quantity) * float(close_rows[0]["close"])
    assert final_nav["market_value"] == pytest.approx(round(expected_market_value, 4), abs=0.001)
    assert final_nav["total_asset"] == pytest.approx(final_nav["cash"] + final_nav["market_value"], abs=0.001)
    assert final_nav["nav"] == pytest.approx(final_nav["total_asset"] / 1000000.0, abs=0.000001)

    assert mutate_prices_after(repository, end_date) > 0
    changed = backtest.run("2024-01-02", end_date, scores_by_date, initial_cash=1000000.0)
    assert_same_backtest_result(baseline, changed)


def test_end_date_rebalance_does_not_require_future_price_rows(tmp_path: Path):
    repository, backtest = build_backtest(
        tmp_path,
        top_n=2,
        single_stock_weight_limit=0.2,
        data_end_date="2024-04-01",
    )
    scores_by_date = {
        "2024-01-31": fixed_scores("600001", "600002"),
        "2024-02-29": fixed_scores("600001", "600002"),
        "2024-03-29": fixed_scores("600002", "600003"),
    }
    end_date = "2024-04-01"
    result = backtest.run("2024-01-02", end_date, scores_by_date, initial_cash=1000000.0)

    future_rows = repository.fetch_dicts(
        "select count(*) as count from daily_bar where trade_date > ?",
        [end_date],
    )
    assert int(future_rows[0]["count"]) == 0
    assert result["nav"][-1]["trade_date"] == end_date
    end_date_orders = [
        order for order in result["orders"]
        if order["signal_date"] == "2024-03-29"
    ]
    assert end_date_orders
    assert {order["trade_date"] for order in end_date_orders} == {end_date}
    assert {order["side"] for order in end_date_orders} == {"buy", "sell"}
    assert result["holdings"]
    assert result["nav"][-1]["cash"] >= 0


def test_month_end_signal_is_not_executed_after_end_date(tmp_path: Path):
    repository, backtest = build_backtest(
        tmp_path,
        top_n=2,
        single_stock_weight_limit=0.2,
        data_end_date="2024-04-30",
    )
    scores_by_date = {
        "2024-01-31": fixed_scores("600001", "600002"),
        "2024-02-29": fixed_scores("600001", "600002"),
        "2024-03-29": fixed_scores("600002", "600003"),
    }
    end_date = "2024-03-29"
    baseline = backtest.run("2024-01-02", end_date, scores_by_date, initial_cash=1000000.0)

    assert baseline["nav"][-1]["trade_date"] == end_date
    assert all(order["trade_date"] <= end_date for order in baseline["orders"])
    assert all(order["signal_date"] != "2024-03-29" for order in baseline["orders"])

    # 2024-04-01 是最后一个月末信号的下一个交易日，已在请求窗口之外；
    # 该日及之后的行情不得影响回测结果。
    assert mutate_prices_after(repository, end_date) > 0
    changed = backtest.run("2024-01-02", end_date, scores_by_date, initial_cash=1000000.0)
    assert_same_backtest_result(baseline, changed)
