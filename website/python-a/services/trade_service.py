from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage_service import JsonStore, filter_by_date, new_id, now_iso


TRADES_FILE = "trades.json"
DRAFTS_FILE = "parse_drafts.json"


class TradeService:
    def __init__(self, store: JsonStore):
        self.store = store

    def list_trades(self, date_value: Optional[str] = None) -> List[Dict[str, Any]]:
        return filter_by_date(self.store.read_list(TRADES_FILE), date_value)

    def add_trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.store.read_list(TRADES_FILE)
        trade_datetime = str(payload.get("trade_datetime") or "").strip()
        if not trade_datetime:
            raise ValueError("trade_datetime is required")
        trade_date = str(payload.get("trade_date") or trade_datetime[:10])
        row = {
            "id": payload.get("id") or new_id("tr", trade_date, len(rows) + 1),
            "trade_datetime": trade_datetime,
            "trade_date": trade_date,
            "stock_code": str(payload.get("stock_code") or "").strip(),
            "stock_name": str(payload.get("stock_name") or "").strip(),
            "side": self._normalize_side(payload.get("side")),
            "price": self._number(payload.get("price"), "成交价格"),
            "quantity": int(self._number(payload.get("quantity"), "成交数量")),
            "amount": self._number(payload.get("amount"), "成交金额"),
            "fee": self._optional_number(payload.get("fee")),
            "stamp_tax": self._optional_number(payload.get("stamp_tax")),
            "transfer_fee": self._optional_number(payload.get("transfer_fee")),
            "reason": str(payload.get("reason") or "").strip(),
            "plan": str(payload.get("plan") or "").strip(),
            "emotion": str(payload.get("emotion") or "").strip(),
            "planned_trade": payload.get("planned_trade"),
            "source": str(payload.get("source") or "manual"),
            "confirmed": bool(payload.get("confirmed", True)),
            "created_at": payload.get("created_at") or now_iso(),
        }
        if not row["stock_name"]:
            raise ValueError("stock_name is required")
        return self.store.append_row(TRADES_FILE, row)

    def create_parse_draft(self, draft_type: str, trade_date: str, parsed: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        rows = self.store.read_list(DRAFTS_FILE)
        if draft_type not in {"account_screenshot", "trades_screenshot"}:
            raise ValueError("解析草稿类型错误")
        row = {
            "id": new_id("pd", trade_date, len(rows) + 1),
            "type": draft_type,
            "trade_date": trade_date,
            "status": "pending",
            "parsed": parsed,
            "warnings": warnings,
            "created_at": now_iso(),
        }
        return self.store.append_row(DRAFTS_FILE, row)

    def list_parse_drafts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.store.read_list(DRAFTS_FILE)
        if status:
            return [row for row in rows if row.get("status") == status]
        return rows

    def confirm_draft(self, draft_id: str, confirmed_payload: Dict[str, Any]) -> Dict[str, Any]:
        drafts = self.store.read_list(DRAFTS_FILE)
        draft = self._find_draft(drafts, draft_id)
        created_trades = []
        if draft["type"] == "trades_screenshot":
            for trade in confirmed_payload.get("trades") or []:
                trade["source"] = "ai_parse"
                created_trades.append(self.add_trade(trade))
        draft["status"] = "confirmed"
        draft["confirmed_payload"] = confirmed_payload
        draft["confirmed_at"] = now_iso()
        self.store.write_list(DRAFTS_FILE, drafts)
        return {"draft": draft, "created_trades": created_trades}

    def reject_draft(self, draft_id: str) -> Dict[str, Any]:
        drafts = self.store.read_list(DRAFTS_FILE)
        draft = self._find_draft(drafts, draft_id)
        draft["status"] = "rejected"
        draft["rejected_at"] = now_iso()
        self.store.write_list(DRAFTS_FILE, drafts)
        return draft

    def _find_draft(self, drafts: List[Dict[str, Any]], draft_id: str) -> Dict[str, Any]:
        for draft in drafts:
            if draft.get("id") == draft_id:
                return draft
        raise ValueError("解析草稿不存在")

    def _normalize_side(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"buy", "买", "买入"}:
            return "buy"
        if text in {"sell", "卖", "卖出"}:
            return "sell"
        raise ValueError("交易方向必须是买入或卖出")

    def _number(self, value: Any, label: str) -> float:
        number = self._optional_number(value)
        if number is None:
            raise ValueError(f"{label}必须是数字")
        return number

    def _optional_number(self, value: Any):
        if value in (None, ""):
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"数值字段格式错误：{value}") from exc
