"""月末调仓回测 `BacktestService`。

执行口径（都会被写进报告偏差披露）：

- 信号：月末交易日的评分，在**下一个**交易日成交，信号日只用当日及以前的数据；
- 价格：成交价取次日开盘价加 0.1% 滑点（对应 `cost_model.yaml` 的 10bps），
  而不是分钟级 VWAP；
- 费用：买入按 0.025% 佣金，卖出按 0.025% 佣金 + 0.05% 印花税；`min_commission`
  与过户费没有实现，小额交易的成本会被低估；
- 数量：按 100 股整手下取整，不检查涨跌停与停牌，现金不足时自动缩量，缩到 0 手则
  记一笔 `rejected` 订单；
- 净值：每个交易日按收盘价重估持仓，`nav = 总资产 / initial_cash`。

回测窗口外的价格永不参与计算（`_scheduled_rebalances` 会丢弃执行日超出 `end_date`
的信号），避免引入未来数据。
"""

from typing import Dict, List
from uuid import uuid4

from quant.calendar.service import TradingCalendarService
from quant.portfolio.service import PortfolioService
from quant.storage.repository import QuantRepository


class BacktestService:
    """按月末信号在次日开盘调仓的简化回测器。"""

    def __init__(self, repository: QuantRepository, calendar: TradingCalendarService, portfolio: PortfolioService):
        """注入依赖。

        Args:
            repository: 读取交易日历与开/收盘价的仓储。
            calendar: 提供月末交易日与下一交易日的日历服务。
            portfolio: 把评分转成目标权重的组合服务。
        """
        self.repository = repository
        self.calendar = calendar
        self.portfolio = portfolio

    def run(
        self,
        start_date: str,
        end_date: str,
        scores_by_date: Dict[str, List[Dict[str, object]]],
        initial_cash: float,
    ) -> Dict[str, object]:
        """执行回测并返回净值曲线、成交明细与期末持仓。

        Args:
            start_date: 回测区间起（含）。
            end_date: 回测区间止（含）；超出该日的信号与价格都丢弃。
            scores_by_date: 信号日 → 评分行列表；只有其中被排进再平衡计划的日期会被使用。
            initial_cash: 初始资金，单位人民币元，同时作为净值分母。

        Returns:
            `experiment_id`（`bt-` 前缀）、`initial_cash`、逐交易日的 `nav`（含现金、
            市值、总资产与净值）、`orders` 与期末 `holdings`（代码 → 股数）。

        Raises:
            ValueError: 成交日缺少开/收盘价（`Missing open/close price`）。
            ZeroDivisionError: `initial_cash` 为 0 时计算净值会除零。
        """
        experiment_id = f"bt-{uuid4().hex[:12]}"
        rebalances_by_execution_date = self._scheduled_rebalances(start_date, end_date, scores_by_date)
        cash = initial_cash
        holdings: Dict[str, float] = {}
        orders = []
        nav = []

        for trade_date in self._trade_dates(start_date, end_date):
            for signal_date in rebalances_by_execution_date.get(trade_date, []):
                rebalance_orders = self._execute_rebalance(
                    signal_date,
                    trade_date,
                    scores_by_date[signal_date],
                    cash,
                    holdings,
                )
                cash = rebalance_orders["cash"]
                orders.extend(rebalance_orders["orders"])

            market_value = sum(quantity * self._close_price(trade_date, code) for code, quantity in holdings.items())
            total_asset = cash + market_value
            nav.append({
                "trade_date": trade_date,
                "cash": round(cash, 4),
                "market_value": round(market_value, 4),
                "total_asset": round(total_asset, 4),
                "nav": round(total_asset / initial_cash, 6),
            })

        return {
            "experiment_id": experiment_id,
            "initial_cash": initial_cash,
            "nav": nav,
            "orders": orders,
            "holdings": holdings,
        }

    def _scheduled_rebalances(
        self,
        start_date: str,
        end_date: str,
        scores_by_date: Dict[str, List[Dict[str, object]]],
    ) -> Dict[str, List[str]]:
        """把月末信号映射成"执行日 → 信号日列表"。

        没有评分的信号日直接跳过；`next_trade_date` 缺失（窗口内最后一天）或执行日
        已超出 `end_date` 的信号也丢弃——这是回测不使用未来价格的关键一步。

        Args:
            start_date: 区间起（含），用于查询月末交易日。
            end_date: 区间止（含），也是允许的最晚执行日。
            scores_by_date: 可用的信号日评分。

        Returns:
            执行日 → 信号日列表的映射；同一执行日理论上只对应一个信号日，
            用列表保存以便未来支持多信号叠加。
        """
        scheduled: Dict[str, List[str]] = {}
        for signal_date in self.calendar.month_end_trade_dates(start_date, end_date):
            if signal_date not in scores_by_date:
                continue
            try:
                execution_date = self.calendar.next_trade_date(signal_date)
            except ValueError:
                continue
            if execution_date > end_date:
                # Never consume a session beyond the requested window; doing so
                # would make the backtest depend on future prices.
                continue
            scheduled.setdefault(execution_date, []).append(signal_date)
        return scheduled

    def _trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """返回区间内的交易日序列（升序，来自 `trade_calendar`）。"""
        rows = self.repository.fetch_dicts(
            "select trade_date from trade_calendar where trade_date between ? and ? order by trade_date",
            [start_date, end_date],
        )
        return [str(row["trade_date"]) for row in rows]

    def _execute_rebalance(
        self,
        signal_date: str,
        trade_date: str,
        scores: List[Dict[str, object]],
        cash: float,
        holdings: Dict[str, float],
    ) -> Dict[str, object]:
        """在一个成交日完成一次调仓，返回更新后的现金与当日订单。

        先按目标池卖出不在池内的持仓，再对每只目标股计算与现有持仓的差额并按需买卖；
        组合市值用**信号日**收盘价估算，确保目标权重不依赖成交日之后的任何价格。
        目标股数按 100 股整手下取整，价格高于目标金额时得到 0 手、不买入。

        Args:
            signal_date: 产生评分的月末交易日。
            trade_date: 实际成交日（信号日的下一个交易日）。
            scores: 该信号日的评分行，用于生成目标权重。
            cash: 调仓前现金。
            holdings: 调仓前持仓（代码 → 股数），本方法会原地修改。

        Returns:
            `{"cash": 新现金, "orders": 本次产生的订单列表}`。

        Raises:
            ValueError: 成交日缺少开盘价（估值/买入价）。
        """
        targets = self.portfolio.build_targets(scores)
        target_codes = {str(target["code"]) for target in targets}
        orders = []
        portfolio_value = cash + sum(
            quantity * self._close_price(signal_date, code)
            for code, quantity in holdings.items()
        )

        for code, quantity in list(holdings.items()):
            if code not in target_codes and quantity > 0:
                cash = self._sell(signal_date, trade_date, code, quantity, cash, holdings, orders)

        for target in targets:
            code = str(target["code"])
            price = self._open_price(trade_date, code)
            target_amount = portfolio_value * float(target["target_weight"])
            target_quantity = int(target_amount / price / 100) * 100
            current_quantity = holdings.get(code, 0)
            delta = target_quantity - current_quantity
            if delta > 0:
                cash = self._buy(signal_date, trade_date, code, delta, price, cash, holdings, orders)
            elif delta < 0:
                cash = self._sell(signal_date, trade_date, code, abs(delta), cash, holdings, orders)

        return {"cash": cash, "orders": orders}

    def _buy(
        self,
        signal_date: str,
        trade_date: str,
        code: str,
        quantity: float,
        price: float,
        cash: float,
        holdings: Dict[str, float],
        orders: List[Dict[str, object]],
    ) -> float:
        """按开盘价买入，现金不足时自动缩量到可负担的整手数。

        买入成本 = 股数 × 价格 × (1 + 0.00025)，只计佣金；`min_commission` 与过户费
        都未实现，小额交易成本偏低。数量为 0 或缩量后不足 1 手时记一笔
        `rejected` 订单并原样返回现金。

        Args:
            signal_date: 信号日，用于订单编号与回溯。
            trade_date: 成交日。
            code: 股票代码。
            quantity: 期望买入股数（调用方已按整手算出差值）。
            price: 成交价，通常来自 `_open_price`。
            cash: 可用现金。
            holdings: 持仓字典，成交时原地累加。
            orders: 订单列表，成交/拒单都会追加。

        Returns:
            买入后的现金。
        """
        if quantity <= 0:
            orders.append(self._order(signal_date, trade_date, code, "buy", 0, price, "rejected", "lot_size_reject"))
            return cash

        cost = quantity * price * (1 + 0.00025)
        if cost > cash:
            affordable_quantity = int(cash / (price * (1 + 0.00025)) / 100) * 100
            if affordable_quantity <= 0:
                orders.append(self._order(signal_date, trade_date, code, "buy", quantity, price, "rejected", "cash_not_enough"))
                return cash
            quantity = min(quantity, affordable_quantity)
            cost = quantity * price * (1 + 0.00025)

        cash -= cost
        holdings[code] = holdings.get(code, 0) + quantity
        orders.append(self._order(signal_date, trade_date, code, "buy", quantity, price, "filled", ""))
        return cash

    def _sell(
        self,
        signal_date: str,
        trade_date: str,
        code: str,
        quantity: float,
        cash: float,
        holdings: Dict[str, float],
        orders: List[Dict[str, object]],
    ) -> float:
        """按开盘价卖出，最多卖到持仓为 0。

        卖出净额 = 股数 × 价格 × (1 - 0.00025 - 0.0005)，即佣金与印花税各扣一次；
        卖完的代码从持仓字典中移除，避免留下 0 股键。数量非正时不产生订单。

        Args:
            signal_date: 信号日，用于订单编号与回溯。
            trade_date: 成交日。
            code: 股票代码。
            quantity: 期望卖出股数，实际卖出不超过当前持仓。
            cash: 卖出前现金。
            holdings: 持仓字典，会原地减少或删除该代码。
            orders: 订单列表，成交时追加。

        Returns:
            卖出后的现金。

        Raises:
            ValueError: 成交日缺少开盘价。
        """
        price = self._open_price(trade_date, code)
        held_quantity = holdings.get(code, 0)
        sell_quantity = min(quantity, held_quantity)
        if sell_quantity <= 0:
            return cash
        cash += sell_quantity * price * (1 - 0.00025 - 0.0005)
        remaining_quantity = held_quantity - sell_quantity
        if remaining_quantity > 0:
            holdings[code] = remaining_quantity
        else:
            holdings.pop(code, None)
        orders.append(self._order(signal_date, trade_date, code, "sell", sell_quantity, price, "filled", ""))
        return cash

    def _open_price(self, trade_date: str, code: str) -> float:
        """取成交日开盘价并叠加 0.1% 滑点。

        滑点是单边固定值（对应 `cost_model.yaml` 的 10bps），不区分买卖方向，
        也不随流动性变化；回测报告会把它列为成交价偏差。

        Args:
            trade_date: 成交日。
            code: 股票代码。

        Returns:
            开盘价 × 1.001。

        Raises:
            ValueError: 该日该股没有行情（`Missing open price`）。
        """
        rows = self.repository.fetch_dicts(
            "select open from daily_bar where trade_date = ? and code = ?",
            [trade_date, code],
        )
        if not rows:
            raise ValueError(f"Missing open price for {code} on {trade_date}")
        return float(rows[0]["open"]) * 1.001

    def _close_price(self, trade_date: str, code: str) -> float:
        """取收盘价用于持仓估值；不加滑点。

        Args:
            trade_date: 估值日。
            code: 股票代码。

        Returns:
            当日收盘价。

        Raises:
            ValueError: 该日该股没有行情（`Missing close price`）。
        """
        rows = self.repository.fetch_dicts(
            "select close from daily_bar where trade_date = ? and code = ?",
            [trade_date, code],
        )
        if not rows:
            raise ValueError(f"Missing close price for {code} on {trade_date}")
        return float(rows[0]["close"])

    def _order(
        self,
        signal_date: str,
        trade_date: str,
        code: str,
        side: str,
        quantity: float,
        price: float,
        status: str,
        reject_reason: str,
    ) -> Dict[str, object]:
        """组装一条订单记录。

        `order_id` 由"信号日-成交日-代码-方向"拼成，同一次回测内唯一；被拒绝的订单
        `filled_quantity` 记 0（数量本身仍保留在 `reject_reason` 的上下文里），
        便于前端区分"想买多少"和"实际成交多少"。

        Args:
            signal_date: 信号日。
            trade_date: 成交日。
            code: 股票代码。
            side: `buy` 或 `sell`。
            quantity: 成交或期望的数量（股）。
            price: 成交价（元）。
            status: `filled` 或 `rejected`。
            reject_reason: 拒单原因，成交时为空串。

        Returns:
            订单字典，含 `order_id`、`filled_quantity`、`filled_price`（4 位小数）、
            `order_status` 与 `reject_reason`。
        """
        return {
            "order_id": f"{signal_date}-{trade_date}-{code}-{side}",
            "signal_date": signal_date,
            "trade_date": trade_date,
            "code": code,
            "side": side,
            "filled_quantity": quantity if status == "filled" else 0,
            "filled_price": round(price, 4),
            "order_status": status,
            "reject_reason": reject_reason,
        }
