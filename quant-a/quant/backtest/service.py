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
        rebalance_dates = [
            day for day in self.calendar.month_end_trade_dates(start_date, end_date)
            if day in scores_by_date
        ]
        cash = initial_cash
        holdings: Dict[str, float] = {}
        orders = []
        nav = []

        for signal_date in rebalance_dates:
            trade_date = self.calendar.next_trade_date(signal_date)
            targets = self.portfolio.build_targets(scores_by_date[signal_date])
            target_codes = {str(target["code"]) for target in targets}

            for code, quantity in list(holdings.items()):
                if code not in target_codes and quantity > 0:
                    price = self._open_price(trade_date, code)
                    cash += quantity * price * (1 - 0.00025 - 0.0005)
                    orders.append(self._order(signal_date, trade_date, code, "sell", quantity, price, "filled", ""))
                    holdings[code] = 0

            portfolio_value = cash + sum(
                quantity * self._close_price(signal_date, code)
                for code, quantity in holdings.items()
            )
            for target in targets:
                code = str(target["code"])
                price = self._open_price(trade_date, code)
                target_amount = portfolio_value * float(target["target_weight"])
                quantity = int(target_amount / price / 100) * 100
                if quantity <= 0:
                    orders.append(self._order(signal_date, trade_date, code, "buy", 0, price, "rejected", "lot_size_reject"))
                    continue

                cost = quantity * price * (1 + 0.00025)
                if cost > cash:
                    orders.append(self._order(signal_date, trade_date, code, "buy", quantity, price, "rejected", "cash_not_enough"))
                    continue

                cash -= cost
                holdings[code] = holdings.get(code, 0) + quantity
                orders.append(self._order(signal_date, trade_date, code, "buy", quantity, price, "filled", ""))

        for day in self.repository.fetch_dicts(
            "select trade_date from trade_calendar where trade_date between ? and ? order by trade_date",
            [start_date, end_date],
        ):
            trade_date = str(day["trade_date"])
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
            return 0.0
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
