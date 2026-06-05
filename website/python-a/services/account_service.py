from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage_service import JsonStore, filter_by_date, new_id, now_iso


CAPITAL_FILE = "capital_flows.json"
SNAPSHOT_FILE = "account_snapshots.json"


class AccountService:
    def __init__(self, store: JsonStore):
        self.store = store

    def list_capital_flows(self) -> List[Dict[str, Any]]:
        return self.store.read_list(CAPITAL_FILE)

    def add_capital_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.list_capital_flows()
        flow_type = str(payload.get("type") or "").strip()
        if flow_type not in {"initial", "deposit", "withdraw", "adjustment"}:
            raise ValueError("资金流水类型必须是 initial、deposit、withdraw 或 adjustment")
        amount = self._number(payload.get("amount"), "金额")
        date_value = str(payload.get("date") or "").strip()
        if not date_value:
            raise ValueError("date is required")
        row = {
            "id": payload.get("id") or new_id("cf", date_value, len(rows) + 1),
            "date": date_value,
            "type": flow_type,
            "amount": amount,
            "note": str(payload.get("note") or "").strip(),
            "created_at": payload.get("created_at") or now_iso(),
        }
        return self.store.append_row(CAPITAL_FILE, row)

    def current_principal(self, through_date: Optional[str] = None) -> float:
        total = 0.0
        for row in self.list_capital_flows():
            if through_date and row.get("date", "") > through_date:
                continue
            amount = self._number(row.get("amount"), "金额")
            flow_type = row.get("type")
            if flow_type in {"initial", "deposit", "adjustment"}:
                total += amount
            elif flow_type == "withdraw":
                total -= amount
        return round(total, 2)

    def add_account_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.store.read_list(SNAPSHOT_FILE)
        trade_date = str(payload.get("trade_date") or payload.get("date") or "").strip()
        if not trade_date:
            raise ValueError("trade_date is required")
        total_assets = self._number(payload.get("total_assets"), "总资产")
        principal = self.current_principal(trade_date)
        account_profit = round(total_assets - principal, 2)
        account_profit_rate = round(account_profit / principal, 4) if principal else 0.0
        row = {
            "id": payload.get("id") or new_id("as", trade_date, len(rows) + 1),
            "trade_date": trade_date,
            "broker": str(payload.get("broker") or "").strip(),
            "account_alias": str(payload.get("account_alias") or "").strip(),
            "total_assets": total_assets,
            "principal": principal,
            "account_profit": account_profit,
            "account_profit_rate": account_profit_rate,
            "daily_profit": self._optional_number(payload.get("daily_profit")),
            "floating_profit": self._optional_number(payload.get("floating_profit")),
            "market_value": self._optional_number(payload.get("market_value")),
            "available_cash": self._optional_number(payload.get("available_cash")),
            "withdrawable_cash": self._optional_number(payload.get("withdrawable_cash")),
            "position_ratio": self._optional_number(payload.get("position_ratio")),
            "positions": payload.get("positions") if isinstance(payload.get("positions"), list) else [],
            "source": str(payload.get("source") or "manual"),
            "confirmed": bool(payload.get("confirmed", True)),
            "note": str(payload.get("note") or "").strip(),
            "created_at": payload.get("created_at") or now_iso(),
        }
        return self.store.append_row(SNAPSHOT_FILE, row)

    def list_account_snapshots(self, date_value: Optional[str] = None) -> List[Dict[str, Any]]:
        return filter_by_date(self.store.read_list(SNAPSHOT_FILE), date_value)

    def dashboard(self, date_value: str) -> Dict[str, Any]:
        snapshots = self.list_account_snapshots(date_value)
        latest = snapshots[-1] if snapshots else None
        return {
            "principal": self.current_principal(date_value),
            "snapshot": latest,
            "snapshots": snapshots,
            "capital_flows": filter_by_date(self.list_capital_flows(), date_value),
        }

    def _number(self, value: Any, label: str) -> float:
        number = self._optional_number(value)
        if number is None:
            raise ValueError(f"{label}必须是数字")
        return number

    def _optional_number(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"数值字段格式错误：{value}") from exc
