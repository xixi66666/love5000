from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set

from .storage_service import JsonStore, filter_by_date, new_id, now_iso


TRADES_FILE = "trades.json"
DRAFTS_FILE = "parse_drafts.json"
_TRADE_LOCK = threading.RLock()


class TradeService:
    def __init__(self, store: JsonStore):
        self.store = store

    def list_trades(self, date_value: Optional[str] = None) -> List[Dict[str, Any]]:
        return filter_by_date(self.store.read_list(TRADES_FILE), date_value)

    def add_trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with _TRADE_LOCK:
            rows = self.store.read_list(TRADES_FILE)
            existing_ids = {row.get("id") for row in rows if isinstance(row, dict)}
            row = self._build_trade(payload, len(rows) + 1, existing_ids)
            return self.store.append_row(TRADES_FILE, row)

    def _build_trade(self, payload: Dict[str, Any], sequence: int, existing_ids: Optional[Set[Any]] = None) -> Dict[str, Any]:
        trade_datetime = str(payload.get("trade_datetime") or "").strip()
        if not trade_datetime:
            raise ValueError("trade_datetime is required")
        trade_date = str(payload.get("trade_date") or trade_datetime[:10])
        row_id = payload.get("id")
        if row_id:
            if existing_ids is not None and row_id in existing_ids:
                raise ValueError(f"交易编号已存在：{row_id}")
        else:
            while True:
                row_id = new_id("tr", trade_date, sequence)
                if existing_ids is None or row_id not in existing_ids:
                    break
                sequence += 1
        row = {
            "id": row_id,
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
        return row

    def create_parse_draft(self, draft_type: str, trade_date: str, parsed: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        if draft_type not in {"account_screenshot", "trades_screenshot"}:
            raise ValueError("解析草稿类型错误")
        with _TRADE_LOCK:
            rows = self.store.read_list(DRAFTS_FILE)
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
        with _TRADE_LOCK:
            drafts = self.store.read_list(DRAFTS_FILE)
            draft = self._find_draft(drafts, draft_id)
            status = draft.get("status") or "pending"

            if status == "confirmed":
                return {"draft": draft, "created_trades": list(draft.get("created_trades") or [])}

            if status == "confirming":
                created_trades = list(draft.get("created_trades") or [])
                self._append_missing_trades(created_trades)
                draft["status"] = "confirmed"
                draft["confirmed_at"] = now_iso()
                self.store.write_list(DRAFTS_FILE, drafts)
                return {"draft": draft, "created_trades": created_trades}

            if status != "pending":
                raise ValueError("解析草稿当前状态不可确认")

            created_trades = self._build_created_trades(draft, confirmed_payload)
            draft["confirmed_payload"] = confirmed_payload
            draft["created_trades"] = created_trades
            if created_trades:
                draft["status"] = "confirming"
                self.store.write_list(DRAFTS_FILE, drafts)
                self._append_missing_trades(created_trades)
            draft["status"] = "confirmed"
            draft["confirmed_at"] = now_iso()
            self.store.write_list(DRAFTS_FILE, drafts)
            return {"draft": draft, "created_trades": created_trades}

    def reject_draft(self, draft_id: str) -> Dict[str, Any]:
        with _TRADE_LOCK:
            drafts = self.store.read_list(DRAFTS_FILE)
            draft = self._find_draft(drafts, draft_id)
            status = draft.get("status") or "pending"
            if status == "rejected":
                return draft
            if status != "pending":
                raise ValueError("解析草稿当前状态不可驳回")
            draft["status"] = "rejected"
            draft["rejected_at"] = now_iso()
            self.store.write_list(DRAFTS_FILE, drafts)
            return draft

    def _build_created_trades(self, draft: Dict[str, Any], confirmed_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if draft.get("type") != "trades_screenshot":
            return []
        if not isinstance(confirmed_payload, dict):
            raise ValueError("确认内容必须是对象")
        trades = confirmed_payload.get("trades") or []
        if not isinstance(trades, list):
            raise ValueError("trades 必须是数组")
        existing_trades = self.store.read_list(TRADES_FILE)
        existing_ids = {row.get("id") for row in existing_trades if isinstance(row, dict)}
        created_trades = []
        for index, trade in enumerate(trades, start=1):
            if not isinstance(trade, dict):
                raise ValueError("交易记录必须是对象")
            item = dict(trade)
            item["source"] = "ai_parse"
            built = self._build_trade(item, len(existing_trades) + index, existing_ids)
            created_trades.append(built)
            existing_ids.add(built["id"])
        return created_trades

    def _append_missing_trades(self, created_trades: List[Dict[str, Any]]) -> None:
        if not created_trades:
            return
        existing_trades = self.store.read_list(TRADES_FILE)
        known_ids = {row.get("id") for row in existing_trades if isinstance(row, dict)}
        missing = []
        for row in created_trades:
            row_id = row.get("id")
            if row_id is not None and row_id in known_ids:
                continue
            missing.append(row)
            if row_id is not None:
                known_ids.add(row_id)
        if missing:
            self.store.write_list(TRADES_FILE, existing_trades + missing)

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
