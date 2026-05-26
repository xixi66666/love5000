from typing import Dict, List
from uuid import uuid4

from quant.calendar.service import TradingCalendarService
from quant.portfolio.service import PortfolioService
from quant.storage.repository import QuantRepository


class BacktestService:
    def __init__(self, repository: QuantRepository, calendar: TradingCalendarService, portfolio: PortfolioService):
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
        scheduled: Dict[str, List[str]] = {}
        for signal_date in self.calendar.month_end_trade_dates(start_date, end_date):
            if signal_date not in scores_by_date:
                continue
            try:
                execution_date = self.calendar.next_trade_date(signal_date)
            except ValueError:
                continue
            if execution_date > end_date:
                continue
            scheduled.setdefault(execution_date, []).append(signal_date)
        return scheduled

    def _trade_dates(self, start_date: str, end_date: str) -> List[str]:
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
        rows = self.repository.fetch_dicts(
            "select open from daily_bar where trade_date = ? and code = ?",
            [trade_date, code],
        )
        if not rows:
            raise ValueError(f"Missing open price for {code} on {trade_date}")
        return float(rows[0]["open"]) * 1.001

    def _close_price(self, trade_date: str, code: str) -> float:
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
