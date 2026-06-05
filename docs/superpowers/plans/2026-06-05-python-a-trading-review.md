# python-a Trading Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular trading review ledger in `website/python-a` while preserving the existing stock research page and APIs.

**Architecture:** Keep `server.py` as the HTTP/static entry point, but move ledger, trade, draft, vision parsing, stock matching, AI review, and Obsidian responsibilities into focused `services/*.py` modules. Store structured data as JSON under `obsidian-vault/A股AI/data/`, and write readable review files into Obsidian Markdown.

**Tech Stack:** Python 3 standard library, `unittest`, `http.server`, JSON files, native HTML/CSS/JavaScript, existing DeepSeek text API support, optional external vision model via `VISION_API_KEY`.

---

## Scope Check

This plan implements the first usable version of the confirmed design:

- Existing stock research UI remains the default view.
- Existing APIs stay compatible: `/api/health`, `/api/watchlist`, `/api/stock`, `/api/ai/dimension-analysis`, `/api/obsidian/stock-daily-review`, `/api/obsidian/daily-review`.
- New trading review API and UI are added.
- Vision parsing is implemented as a configurable service. If no vision key is configured, upload endpoints return a clear error and manual entry still works.
- First version does not add SQLite, backtesting, strategy statistics, or saved original screenshots.

## Files

Create:

- `website/python-a/services/__init__.py`: marks service package.
- `website/python-a/services/storage_service.py`: JSON store, atomic writes, ID generation, date filtering.
- `website/python-a/services/account_service.py`: capital flows, account snapshots, principal and account profit calculations.
- `website/python-a/services/trade_service.py`: confirmed trades, parse drafts, trade filtering, draft confirmation/rejection.
- `website/python-a/services/stock_match_service.py`: local stock-name-to-code matching and mapping persistence.
- `website/python-a/services/vision_parse_service.py`: image parsing API client and disabled-state behavior.
- `website/python-a/services/ai_review_service.py`: daily review and insight update payload construction.
- `website/python-a/services/obsidian_service.py`: daily review, stock long-term note, and insight index writes.
- `website/python-a/tests/__init__.py`: test package marker.
- `website/python-a/tests/test_storage_service.py`
- `website/python-a/tests/test_account_service.py`
- `website/python-a/tests/test_trade_service.py`
- `website/python-a/tests/test_stock_match_service.py`
- `website/python-a/tests/test_obsidian_service.py`
- `website/python-a/tests/test_vision_parse_service.py`

Modify:

- `website/python-a/server.py`: import services, add `/api/trading/**` routes, keep old routes.
- `website/python-a/index.html`: add top-level tabs and trading review markup while keeping old research markup.
- `website/python-a/app.js`: add trading state, API calls, renderers, form handlers, file upload handlers.
- `website/python-a/styles.css`: add trading review styles without removing existing styles. Preserve any unrelated existing user edits.
- `website/python-a/README.md`: document trading review workflow, privacy behavior, and new API list.
- `AGENTS.md`: update `python-a` API list and Obsidian structure if implementation changes project conventions.

---

### Task 1: Storage Service And Test Scaffold

**Files:**
- Create: `website/python-a/services/__init__.py`
- Create: `website/python-a/services/storage_service.py`
- Create: `website/python-a/tests/__init__.py`
- Create: `website/python-a/tests/test_storage_service.py`

- [ ] **Step 1: Write the failing storage tests**

Create `website/python-a/tests/test_storage_service.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from services.storage_service import JsonStore, filter_by_date, new_id


class JsonStoreTests(unittest.TestCase):
    def test_read_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonStore(Path(temp_dir))

            self.assertEqual(store.read_list("trades.json"), [])

    def test_write_list_creates_parent_and_round_trips_utf8(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonStore(Path(temp_dir))
            rows = [{"stock_name": "大唐发电", "amount": 2697.0}]

            store.write_list("nested/trades.json", rows)

            self.assertEqual(store.read_list("nested/trades.json"), rows)

    def test_corrupt_json_is_backed_up_and_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "trades.json"
            path.write_text("{broken", encoding="utf-8")
            store = JsonStore(root)

            with self.assertRaises(ValueError) as context:
                store.read_list("trades.json")

            self.assertIn("JSON 文件损坏", str(context.exception))
            backups = list(root.glob("trades.json.corrupt-*"))
            self.assertEqual(len(backups), 1)

    def test_filter_by_date_matches_trade_date_and_date(self):
        rows = [
            {"trade_date": "2026-06-05", "id": "a"},
            {"date": "2026-06-05", "id": "b"},
            {"trade_date": "2026-06-04", "id": "c"},
        ]

        result = filter_by_date(rows, "2026-06-05")

        self.assertEqual([row["id"] for row in result], ["a", "b"])

    def test_new_id_uses_prefix_and_yyyymmdd_date(self):
        value = new_id("tr", "2026-06-05", 7)

        self.assertEqual(value, "tr_20260605_007")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_storage_service -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services'`.

- [ ] **Step 3: Add the service package marker**

Create `website/python-a/services/__init__.py`:

```python
"""服务层模块，承载 python-a 的可测试业务逻辑。"""
```

Create `website/python-a/tests/__init__.py`:

```python
"""python-a 单元测试。"""
```

- [ ] **Step 4: Implement `storage_service.py`**

Create `website/python-a/services/storage_service.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str, date_value: Optional[str], sequence: int) -> str:
    clean_date = (date_value or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
    return f"{prefix}_{clean_date}_{sequence:03d}"


def filter_by_date(rows: List[Dict[str, Any]], date_value: Optional[str]) -> List[Dict[str, Any]]:
    if not date_value:
        return list(rows)
    return [
        row
        for row in rows
        if row.get("trade_date") == date_value or row.get("date") == date_value
    ]


class JsonStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, relative_path: str) -> Path:
        return self.root / relative_path

    def read_list(self, relative_path: str) -> List[Dict[str, Any]]:
        path = self.path_for(relative_path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            backup = path.with_name(f"{path.name}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            path.replace(backup)
            raise ValueError(f"JSON 文件损坏，已备份到 {backup}") from exc
        if not isinstance(data, list):
            raise ValueError(f"{relative_path} 必须是 JSON 数组")
        return data

    def write_list(self, relative_path: str, rows: List[Dict[str, Any]]) -> None:
        path = self.path_for(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp_path), str(path))

    def append_row(self, relative_path: str, row: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.read_list(relative_path)
        rows.append(row)
        self.write_list(relative_path, rows)
        return row
```

- [ ] **Step 5: Run storage tests**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_storage_service -v
```

Expected: PASS all 5 tests.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add website/python-a/services/__init__.py website/python-a/services/storage_service.py website/python-a/tests/__init__.py website/python-a/tests/test_storage_service.py
git commit -m "feat: add python-a json storage service"
```

---

### Task 2: Account Ledger Service

**Files:**
- Create: `website/python-a/services/account_service.py`
- Create: `website/python-a/tests/test_account_service.py`

- [ ] **Step 1: Write the failing account tests**

Create `website/python-a/tests/test_account_service.py`:

```python
import tempfile
import unittest
from pathlib import Path

from services.account_service import AccountService
from services.storage_service import JsonStore


class AccountServiceTests(unittest.TestCase):
    def make_service(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        store = JsonStore(Path(self.temp_dir.name))
        return AccountService(store)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_capital_flow_calculates_principal(self):
        service = self.make_service()

        service.add_capital_flow({"date": "2026-06-01", "type": "initial", "amount": 10000})
        service.add_capital_flow({"date": "2026-06-03", "type": "deposit", "amount": 6000})
        service.add_capital_flow({"date": "2026-06-04", "type": "withdraw", "amount": 1000})
        service.add_capital_flow({"date": "2026-06-05", "type": "adjustment", "amount": -200})

        self.assertEqual(service.current_principal(), 14800.0)

    def test_add_snapshot_calculates_profit_from_principal(self):
        service = self.make_service()
        service.add_capital_flow({"date": "2026-06-01", "type": "initial", "amount": 16000})

        snapshot = service.add_account_snapshot(
            {
                "trade_date": "2026-06-05",
                "broker": "西南证券",
                "account_alias": "**7763",
                "total_assets": 15909.86,
                "daily_profit": -378,
                "floating_profit": 391.57,
                "market_value": 15480,
                "available_cash": 429.86,
                "withdrawable_cash": 429.86,
                "position_ratio": 0.973,
            }
        )

        self.assertEqual(snapshot["principal"], 16000.0)
        self.assertEqual(snapshot["account_profit"], -90.14)
        self.assertEqual(snapshot["account_profit_rate"], -0.0056)
        self.assertTrue(snapshot["confirmed"])

    def test_dashboard_returns_latest_snapshot_for_date(self):
        service = self.make_service()
        service.add_capital_flow({"date": "2026-06-01", "type": "initial", "amount": 16000})
        service.add_account_snapshot({"trade_date": "2026-06-04", "total_assets": 15000})
        service.add_account_snapshot({"trade_date": "2026-06-05", "total_assets": 15909.86})

        dashboard = service.dashboard("2026-06-05")

        self.assertEqual(dashboard["principal"], 16000.0)
        self.assertEqual(dashboard["snapshot"]["total_assets"], 15909.86)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_account_service -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.account_service'`.

- [ ] **Step 3: Implement `account_service.py`**

Create `website/python-a/services/account_service.py`:

```python
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
```

- [ ] **Step 4: Run account tests**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_account_service -v
```

Expected: PASS all 3 tests.

- [ ] **Step 5: Run storage and account tests together**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_storage_service tests.test_account_service -v
```

Expected: PASS all tests.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add website/python-a/services/account_service.py website/python-a/tests/test_account_service.py
git commit -m "feat: add python-a account ledger service"
```

---

### Task 3: Trade Records, Parse Drafts, And Stock Matching

**Files:**
- Create: `website/python-a/services/trade_service.py`
- Create: `website/python-a/services/stock_match_service.py`
- Create: `website/python-a/tests/test_trade_service.py`
- Create: `website/python-a/tests/test_stock_match_service.py`

- [ ] **Step 1: Write trade service tests**

Create `website/python-a/tests/test_trade_service.py`:

```python
import tempfile
import unittest
from pathlib import Path

from services.storage_service import JsonStore
from services.trade_service import TradeService


class TradeServiceTests(unittest.TestCase):
    def make_service(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        return TradeService(JsonStore(Path(self.temp_dir.name)))

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_add_trade_normalizes_side_and_date(self):
        service = self.make_service()

        trade = service.add_trade(
            {
                "trade_datetime": "2026-06-04T14:40:20+08:00",
                "stock_code": "601991",
                "stock_name": "大唐发电",
                "side": "买入",
                "price": 8.99,
                "quantity": 300,
                "amount": 2697,
            }
        )

        self.assertEqual(trade["trade_date"], "2026-06-04")
        self.assertEqual(trade["side"], "buy")
        self.assertEqual(trade["stock_code"], "601991")

    def test_list_trades_filters_by_date(self):
        service = self.make_service()
        service.add_trade({"trade_datetime": "2026-06-04T14:40:20+08:00", "stock_name": "大唐发电", "side": "buy", "price": 8.99, "quantity": 300, "amount": 2697})
        service.add_trade({"trade_datetime": "2026-06-03T10:57:52+08:00", "stock_name": "大唐发电", "side": "buy", "price": 8.5, "quantity": 700, "amount": 5950})

        rows = service.list_trades("2026-06-04")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 2697.0)

    def test_create_and_confirm_trade_draft(self):
        service = self.make_service()
        draft = service.create_parse_draft(
            "trades_screenshot",
            "2026-06-05",
            {
                "trades": [
                    {"stock_name": "大唐发电", "side": "买入", "trade_datetime": "2026-06-04T14:40:20+08:00", "price": 8.99, "quantity": 300, "amount": 2697}
                ]
            },
            ["股票代码未唯一匹配"],
        )

        result = service.confirm_draft(
            draft["id"],
            {
                "trades": [
                    {"stock_code": "601991", "stock_name": "大唐发电", "side": "buy", "trade_datetime": "2026-06-04T14:40:20+08:00", "price": 8.99, "quantity": 300, "amount": 2697}
                ]
            },
        )

        self.assertEqual(result["draft"]["status"], "confirmed")
        self.assertEqual(result["created_trades"][0]["stock_code"], "601991")

    def test_reject_draft_marks_status(self):
        service = self.make_service()
        draft = service.create_parse_draft("account_screenshot", "2026-06-05", {"total_assets": 15909.86}, [])

        rejected = service.reject_draft(draft["id"])

        self.assertEqual(rejected["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write stock matching tests**

Create `website/python-a/tests/test_stock_match_service.py`:

```python
import tempfile
import unittest
from pathlib import Path

from services.stock_match_service import StockMatchService
from services.storage_service import JsonStore


class StockMatchServiceTests(unittest.TestCase):
    def make_service(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        store = JsonStore(Path(self.temp_dir.name))
        return StockMatchService(
            store,
            seed_rows=[
                {"stock_code": "601991", "stock_name": "大唐发电"},
                {"stock_code": "001300", "stock_name": "三柏硕"},
                {"stock_code": "000001", "stock_name": "平安银行"},
            ],
        )

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_unique_match_returns_matched_status(self):
        service = self.make_service()

        result = service.match_name("大唐发电")

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["stock_code"], "601991")

    def test_unknown_name_returns_unmatched(self):
        service = self.make_service()

        result = service.match_name("不存在股票")

        self.assertEqual(result["status"], "unmatched")

    def test_confirm_mapping_persists_manual_choice(self):
        service = self.make_service()

        service.confirm_mapping("通信ETF国泰", "159510")
        result = service.match_name("通信ETF国泰")

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["stock_code"], "159510")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_trade_service tests.test_stock_match_service -v
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement `trade_service.py`**

Create `website/python-a/services/trade_service.py`:

```python
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
```

- [ ] **Step 5: Implement `stock_match_service.py`**

Create `website/python-a/services/stock_match_service.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage_service import JsonStore


MAPPING_FILE = "stock_name_mappings.json"


class StockMatchService:
    def __init__(self, store: JsonStore, seed_rows: Optional[List[Dict[str, Any]]] = None):
        self.store = store
        self.seed_rows = seed_rows or []

    def match_name(self, stock_name: str) -> Dict[str, Any]:
        name = stock_name.strip()
        if not name:
            return {"status": "unmatched", "candidates": []}
        candidates = self._all_candidates(name)
        exact = [item for item in candidates if item.get("stock_name") == name]
        if len(exact) == 1:
            return {"status": "matched", **exact[0], "candidates": exact}
        if len(exact) > 1:
            return {"status": "multiple", "candidates": exact}
        fuzzy = [item for item in candidates if name in item.get("stock_name", "") or item.get("stock_name", "") in name]
        if len(fuzzy) == 1:
            return {"status": "matched", **fuzzy[0], "candidates": fuzzy}
        if len(fuzzy) > 1:
            return {"status": "multiple", "candidates": fuzzy}
        return {"status": "unmatched", "candidates": []}

    def confirm_mapping(self, stock_name: str, stock_code: str) -> Dict[str, str]:
        name = stock_name.strip()
        code = stock_code.strip()
        if not name or not code:
            raise ValueError("股票名称和代码都不能为空")
        rows = self.store.read_list(MAPPING_FILE)
        rows = [row for row in rows if row.get("stock_name") != name]
        row = {"stock_name": name, "stock_code": code}
        rows.append(row)
        self.store.write_list(MAPPING_FILE, rows)
        return row

    def _all_candidates(self, stock_name: str) -> List[Dict[str, Any]]:
        rows = []
        rows.extend(self.store.read_list(MAPPING_FILE))
        rows.extend(self.seed_rows)
        seen = set()
        unique = []
        for row in rows:
            key = (row.get("stock_code"), row.get("stock_name"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique
```

- [ ] **Step 6: Run trade and matching tests**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_trade_service tests.test_stock_match_service -v
```

Expected: PASS all tests.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add website/python-a/services/trade_service.py website/python-a/services/stock_match_service.py website/python-a/tests/test_trade_service.py website/python-a/tests/test_stock_match_service.py
git commit -m "feat: add python-a trade and stock matching services"
```

---

### Task 4: Obsidian Trading Review Service

**Files:**
- Create: `website/python-a/services/obsidian_service.py`
- Create: `website/python-a/tests/test_obsidian_service.py`

- [ ] **Step 1: Write Obsidian service tests**

Create `website/python-a/tests/test_obsidian_service.py`:

```python
import tempfile
import unittest
from pathlib import Path

from services.obsidian_service import ObsidianTradingService


class ObsidianTradingServiceTests(unittest.TestCase):
    def test_write_daily_review_creates_markdown_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ObsidianTradingService(Path(temp_dir))

            result = service.write_daily_review(
                "2026-06-05",
                {"total_assets": 15909.86, "account_profit": -90.14},
                [{"stock_code": "601991", "stock_name": "大唐发电", "side": "buy", "price": 8.99, "quantity": 300}],
                {"summary": "今天冲动买入。", "lesson": "先写计划再下单。"},
            )

            path = Path(result["daily_review_path"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("# 2026-06-05 交易复盘", content)
            self.assertIn("大唐发电", content)
            self.assertIn("非投资建议", content)

    def test_update_stock_note_preserves_manual_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_file = root / "股票" / "601991-大唐发电.md"
            stock_file.parent.mkdir(parents=True)
            stock_file.write_text(
                "# 601991 大唐发电\n\n## 系统维护区\n\n旧内容\n\n## 我的手写心得\n\n这里别覆盖。\n",
                encoding="utf-8",
            )
            service = ObsidianTradingService(root)

            service.update_stock_note(
                "601991",
                "大唐发电",
                [{"trade_date": "2026-06-05", "side": "buy", "price": 8.99, "quantity": 300}],
                ["2026-06-05-交易复盘.md"],
                "这只股票容易追高，需要等待计划内位置。",
            )

            content = stock_file.read_text(encoding="utf-8")
            self.assertIn("这只股票容易追高", content)
            self.assertIn("这里别覆盖。", content)

    def test_update_insight_index_writes_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ObsidianTradingService(Path(temp_dir))

            result = service.update_insight_index(
                {
                    "summary": "本周最大问题是仓位太满。",
                    "mistakes": ["追高", "没写卖出条件"],
                    "effective_patterns": ["分批买入"],
                    "discipline": ["下单前截图复核"],
                    "position_lessons": ["单票仓位不要超过计划"],
                    "buy_checklist": ["板块是否共振"],
                    "sell_checklist": ["跌破条件是否触发"],
                    "hypotheses": ["电力板块持续性需要成交额验证"],
                }
            )

            content = Path(result["insight_path"]).read_text(encoding="utf-8")
            self.assertIn("## 高频错误模式", content)
            self.assertIn("追高", content)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_obsidian_service -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement `obsidian_service.py`**

Create `website/python-a/services/obsidian_service.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .storage_service import now_iso


class ObsidianTradingService:
    def __init__(self, vault_root: Path):
        self.vault_root = Path(vault_root)

    def ensure_dirs(self) -> None:
        for name in ["账户", "每日复盘", "股票"]:
            (self.vault_root / name).mkdir(parents=True, exist_ok=True)

    def write_daily_review(self, trade_date: str, snapshot: Dict[str, Any], trades: List[Dict[str, Any]], review: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.vault_root / "每日复盘" / f"{trade_date}-交易复盘.md"
        trade_lines = [
            f"- {item.get('stock_code', '')} {item.get('stock_name', '')} {item.get('side', '')} {item.get('price', '')} x {item.get('quantity', '')}"
            for item in trades
        ]
        markdown = (
            "---\n"
            f"title: {trade_date} 交易复盘\n"
            f"date: {trade_date}\n"
            "review_type: trading_daily_review\n"
            "tags:\n"
            "  - trading-review\n"
            "  - non-investment-advice\n"
            "---\n\n"
            f"# {trade_date} 交易复盘\n\n"
            "## 账户快照\n\n"
            f"- 总资产：{snapshot.get('total_assets', '--')}\n"
            f"- 本金：{snapshot.get('principal', '--')}\n"
            f"- 账户收益：{snapshot.get('account_profit', '--')}\n"
            f"- 当日参考盈亏：{snapshot.get('daily_profit', '--')}\n\n"
            "## 今日交易\n\n"
            f"{chr(10).join(trade_lines) if trade_lines else '- 今日无确认交易'}\n\n"
            "## 今日复盘\n\n"
            f"- 操作总结：{review.get('summary', '')}\n"
            f"- 做对了什么：{review.get('did_well', '')}\n"
            f"- 做错了什么：{review.get('mistake', '')}\n"
            f"- 仓位是否合理：{review.get('position_review', '')}\n"
            f"- 情绪是否影响操作：{review.get('emotion_review', '')}\n"
            f"- 明日观察计划：{review.get('next_plan', '')}\n"
            f"- 自由心得：{review.get('lesson', '')}\n\n"
            "> 本文只用于个人交易复盘和风险提示，非投资建议。\n"
        )
        path.write_text(markdown, encoding="utf-8")
        return {"ok": True, "success": True, "daily_review_path": str(path), "written_at": now_iso()}

    def update_stock_note(self, stock_code: str, stock_name: str, trades: List[Dict[str, Any]], review_links: List[str], ai_summary: str) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.vault_root / "股票" / f"{stock_code}-{stock_name}.md"
        manual_heading = "## 我的手写心得"
        manual_section = f"{manual_heading}\n\n"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if manual_heading in content:
                manual_section = content[content.index(manual_heading):].rstrip() + "\n"
        trade_lines = [
            f"- {item.get('trade_date', '')} {item.get('side', '')} {item.get('price', '')} x {item.get('quantity', '')}"
            for item in trades
        ]
        link_lines = [f"- [[{link}]]" for link in review_links]
        system_section = (
            f"# {stock_code} {stock_name}\n\n"
            "## 系统维护区\n\n"
            "### 交易统计\n\n"
            f"- 已记录交易数：{len(trades)}\n\n"
            "### 最近交易\n\n"
            f"{chr(10).join(trade_lines) if trade_lines else '- 暂无交易'}\n\n"
            "### 复盘索引\n\n"
            f"{chr(10).join(link_lines) if link_lines else '- 暂无复盘'}\n\n"
            "### AI 个股经验摘要\n\n"
            f"{ai_summary or '暂无摘要'}\n\n"
            "### 后续观察计划\n\n"
            "- 等待下一次确认复盘后更新。\n\n"
        )
        path.write_text(system_section + manual_section, encoding="utf-8")
        return {"ok": True, "success": True, "stock_path": str(path), "written_at": now_iso()}

    def update_insight_index(self, insight: Dict[str, Any]) -> Dict[str, Any]:
        self.vault_root.mkdir(parents=True, exist_ok=True)
        path = self.vault_root / "交易心得总纲.md"
        markdown = (
            "# 交易心得总纲\n\n"
            "## 最近更新摘要\n\n"
            f"{insight.get('summary', '')}\n\n"
            "## 高频错误模式\n\n"
            f"{self._bullet_list(insight.get('mistakes'))}\n\n"
            "## 有效操作模式\n\n"
            f"{self._bullet_list(insight.get('effective_patterns'))}\n\n"
            "## 情绪和纪律问题\n\n"
            f"{self._bullet_list(insight.get('discipline'))}\n\n"
            "## 仓位管理教训\n\n"
            f"{self._bullet_list(insight.get('position_lessons'))}\n\n"
            "## 买入前检查清单\n\n"
            f"{self._bullet_list(insight.get('buy_checklist'))}\n\n"
            "## 卖出前检查清单\n\n"
            f"{self._bullet_list(insight.get('sell_checklist'))}\n\n"
            "## 仍待验证的策略假设\n\n"
            f"{self._bullet_list(insight.get('hypotheses'))}\n\n"
            "> 本文件只用于个人复盘，非投资建议。\n"
        )
        path.write_text(markdown, encoding="utf-8")
        return {"ok": True, "success": True, "insight_path": str(path), "written_at": now_iso()}

    def _bullet_list(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "- 暂无"
        return "\n".join(f"- {value}" for value in values)
```

- [ ] **Step 4: Run Obsidian service tests**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_obsidian_service -v
```

Expected: PASS all tests.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add website/python-a/services/obsidian_service.py website/python-a/tests/test_obsidian_service.py
git commit -m "feat: add python-a obsidian trading review service"
```

---

### Task 5: Vision Parse Service With Disabled-State Safety

**Files:**
- Create: `website/python-a/services/vision_parse_service.py`
- Create: `website/python-a/tests/test_vision_parse_service.py`

- [ ] **Step 1: Write vision service tests**

Create `website/python-a/tests/test_vision_parse_service.py`:

```python
import unittest

from services.vision_parse_service import VisionParseService


class VisionParseServiceTests(unittest.TestCase):
    def test_parse_without_api_key_raises_clear_error(self):
        service = VisionParseService(api_key="", api_base="https://example.invalid/v1", model="vision-test")

        with self.assertRaises(ValueError) as context:
            service.parse_account_screenshot(b"fake-image", "image/jpeg")

        self.assertIn("VISION_API_KEY", str(context.exception))

    def test_build_account_prompt_names_required_fields(self):
        service = VisionParseService(api_key="key", api_base="https://example.invalid/v1", model="vision-test")

        prompt = service.account_prompt()

        self.assertIn("总资产", prompt)
        self.assertIn("持仓", prompt)
        self.assertIn("严格 JSON", prompt)

    def test_build_trades_prompt_names_required_fields(self):
        service = VisionParseService(api_key="key", api_base="https://example.invalid/v1", model="vision-test")

        prompt = service.trades_prompt()

        self.assertIn("成交时间", prompt)
        self.assertIn("成交价格", prompt)
        self.assertIn("股票代码缺失", prompt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_vision_parse_service -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement `vision_parse_service.py`**

Create `website/python-a/services/vision_parse_service.py`:

```python
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict


class VisionParseService:
    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.model = model

    def account_prompt(self) -> str:
        return (
            "你是证券账户截图解析助手。请从截图中提取账户资金和持仓信息，输出严格 JSON。"
            "字段包含 broker, account_alias, total_assets, floating_profit, daily_profit, market_value, "
            "available_cash, withdrawable_cash, position_ratio, positions。"
            "positions 每项包含 stock_name, market_value, floating_profit, profit_rate, holding_quantity, "
            "available_quantity, cost_price, current_price。无法识别的字段使用 null，不要编造。"
        )

    def trades_prompt(self) -> str:
        return (
            "你是证券历史成交截图解析助手。请从截图中提取成交记录，输出严格 JSON。"
            "字段包含 date_range 和 trades。trades 每项包含 stock_name, stock_code, side, trade_datetime, "
            "price, quantity, amount。截图中股票代码缺失时 stock_code 使用空字符串，不要猜测代码。"
            "side 只能使用 buy 或 sell。无法识别的字段使用 null，不要编造。"
        )

    def parse_account_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        return self._call_vision(self.account_prompt(), image_bytes, mime_type)

    def parse_trades_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        return self._call_vision(self.trades_prompt(), image_bytes, mime_type)

    def _call_vision(self, prompt: str, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("VISION_API_KEY 未配置，无法使用截图 AI 解析；请使用人工录入或配置视觉模型。")
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.api_base}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"视觉解析请求失败：HTTP {exc.code} {detail}") from exc
        content = response_payload["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return json.loads(content)
        raise RuntimeError("视觉解析响应格式异常")
```

- [ ] **Step 4: Run vision tests**

Run:

```powershell
cd website/python-a
python -m unittest tests.test_vision_parse_service -v
```

Expected: PASS all tests.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add website/python-a/services/vision_parse_service.py website/python-a/tests/test_vision_parse_service.py
git commit -m "feat: add python-a vision parsing service"
```

---

### Task 6: Trading HTTP Routes

**Files:**
- Modify: `website/python-a/server.py`

- [ ] **Step 1: Add service imports and factories near existing constants**

Modify `website/python-a/server.py` near the existing imports and constants:

```python
from services.account_service import AccountService
from services.obsidian_service import ObsidianTradingService
from services.stock_match_service import StockMatchService
from services.storage_service import JsonStore
from services.trade_service import TradeService
from services.vision_parse_service import VisionParseService
```

Add after `OBSIDIAN_ROOT`:

```python
DATA_ROOT = OBSIDIAN_ROOT / "data"
VISION_API_BASE = os.environ.get("VISION_API_BASE", DEEPSEEK_API_BASE).rstrip("/")
VISION_MODEL = os.environ.get("VISION_MODEL", os.environ.get("DEEPSEEK_VISION_MODEL", "gpt-4o-mini"))


def trading_services() -> Dict[str, Any]:
    store = JsonStore(DATA_ROOT)
    return {
        "account": AccountService(store),
        "trade": TradeService(store),
        "stock_match": StockMatchService(store, seed_rows=read_watchlist()),
        "obsidian": ObsidianTradingService(OBSIDIAN_ROOT),
        "vision": VisionParseService(
            api_key=read_local_secret("VISION_API_KEY"),
            api_base=VISION_API_BASE,
            model=VISION_MODEL,
        ),
    }
```

- [ ] **Step 2: Add multipart image reading helper**

Add below `json_response`:

```python
def read_uploaded_image(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("请使用 multipart/form-data 上传截图")
    try:
        import cgi

        form = cgi.FieldStorage(
            fp=handler.rfile,
            headers=handler.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        file_item = form["file"] if "file" in form else None
        if not file_item or not getattr(file_item, "file", None):
            raise ValueError("file is required")
        image_bytes = file_item.file.read()
        mime_type = getattr(file_item, "type", None) or "image/jpeg"
        trade_date = form.getfirst("trade_date") or datetime.now().strftime("%Y-%m-%d")
        return {"image_bytes": image_bytes, "mime_type": mime_type, "trade_date": trade_date}
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"截图上传解析失败：{exc}") from exc
```

- [ ] **Step 3: Add GET trading routes**

In `AShareHandler.do_GET`, before `return super().do_GET()`, add:

```python
        if parsed.path == "/api/trading/dashboard":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [datetime.now().strftime("%Y-%m-%d")])[0]
            services = trading_services()
            account_dashboard = services["account"].dashboard(date_value)
            trades = services["trade"].list_trades(date_value)
            json_response(
                self,
                {
                    "ok": True,
                    "success": True,
                    "date": date_value,
                    "account": account_dashboard,
                    "trades": trades,
                    "parse_drafts": services["trade"].list_parse_drafts("pending"),
                },
            )
            return
        if parsed.path == "/api/trading/capital-flows":
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "flows": services["account"].list_capital_flows()})
            return
        if parsed.path == "/api/trading/account-snapshots":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [None])[0]
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "snapshots": services["account"].list_account_snapshots(date_value)})
            return
        if parsed.path == "/api/trading/trades":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [None])[0]
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "trades": services["trade"].list_trades(date_value)})
            return
        if parsed.path == "/api/trading/parse-drafts":
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "drafts": services["trade"].list_parse_drafts()})
            return
```

- [ ] **Step 4: Add JSON POST trading routes**

In `AShareHandler.do_POST`, after JSON payload parsing routes and before `Not found`, add:

```python
            services = trading_services()
            if parsed.path == "/api/trading/capital-flows":
                json_response(self, {"ok": True, "success": True, "flow": services["account"].add_capital_flow(payload)})
                return
            if parsed.path == "/api/trading/account-snapshots":
                json_response(self, {"ok": True, "success": True, "snapshot": services["account"].add_account_snapshot(payload)})
                return
            if parsed.path == "/api/trading/trades":
                json_response(self, {"ok": True, "success": True, "trade": services["trade"].add_trade(payload)})
                return
            if parsed.path.startswith("/api/trading/parse-drafts/") and parsed.path.endswith("/confirm"):
                draft_id = parsed.path.split("/")[-2]
                result = services["trade"].confirm_draft(draft_id, payload)
                json_response(self, {"ok": True, "success": True, **result})
                return
            if parsed.path.startswith("/api/trading/parse-drafts/") and parsed.path.endswith("/reject"):
                draft_id = parsed.path.split("/")[-2]
                draft = services["trade"].reject_draft(draft_id)
                json_response(self, {"ok": True, "success": True, "draft": draft})
                return
            if parsed.path == "/api/trading/daily-review":
                result = services["obsidian"].write_daily_review(
                    payload.get("date") or datetime.now().strftime("%Y-%m-%d"),
                    payload.get("snapshot") or {},
                    payload.get("trades") or [],
                    payload.get("review") or {},
                )
                json_response(self, result)
                return
            if parsed.path == "/api/trading/insights/update":
                result = services["obsidian"].update_insight_index(payload.get("insight") or payload)
                json_response(self, result)
                return
            if parsed.path == "/api/trading/stock-match":
                result = services["stock_match"].match_name(str(payload.get("stock_name") or ""))
                json_response(self, {"ok": True, "success": True, "match": result})
                return
```

- [ ] **Step 5: Add multipart screenshot routes before JSON parsing**

At the start of `AShareHandler.do_POST`, after `parsed = urllib.parse.urlparse(self.path)` and before reading JSON body, add:

```python
        if parsed.path in {"/api/trading/parse/account-screenshot", "/api/trading/parse/trades-screenshot"}:
            try:
                upload = read_uploaded_image(self)
                services = trading_services()
                if parsed.path.endswith("account-screenshot"):
                    parsed_payload = services["vision"].parse_account_screenshot(upload["image_bytes"], upload["mime_type"])
                    draft = services["trade"].create_parse_draft("account_screenshot", upload["trade_date"], parsed_payload, [])
                else:
                    parsed_payload = services["vision"].parse_trades_screenshot(upload["image_bytes"], upload["mime_type"])
                    warnings = []
                    for trade in parsed_payload.get("trades") or []:
                        if not trade.get("stock_code") and trade.get("stock_name"):
                            match = services["stock_match"].match_name(trade["stock_name"])
                            trade["stock_match"] = match
                            if match.get("status") == "matched":
                                trade["stock_code"] = match.get("stock_code", "")
                            else:
                                warnings.append(f"{trade.get('stock_name')} 股票代码未唯一匹配")
                    draft = services["trade"].create_parse_draft("trades_screenshot", upload["trade_date"], parsed_payload, warnings)
                json_response(self, {"ok": True, "success": True, "draft": draft})
            except Exception as exc:
                json_response(self, {"ok": False, "success": False, "error": str(exc), "message": str(exc)}, status=400)
            return
```

- [ ] **Step 6: Run service tests**

Run:

```powershell
cd website/python-a
python -m unittest discover -s tests -v
```

Expected: PASS all service tests.

- [ ] **Step 7: Start the server and verify old health route**

Run:

```powershell
cd website/python-a
python server.py
```

In another terminal:

```powershell
curl.exe -s http://127.0.0.1:5174/api/health
```

Expected JSON contains `"ok": true` and existing `obsidian_root`.

- [ ] **Step 8: Verify a new route manually**

Run:

```powershell
curl.exe -s "http://127.0.0.1:5174/api/trading/dashboard?date=2026-06-05"
```

Expected JSON contains `"success": true`, `"account"`, `"trades"`, and `"parse_drafts"`.

- [ ] **Step 9: Commit Task 6**

Run:

```powershell
git add website/python-a/server.py
git commit -m "feat: add python-a trading review api routes"
```

---

### Task 7: Frontend Tabs And Trading Review Markup

**Files:**
- Modify: `website/python-a/index.html`
- Modify: `website/python-a/styles.css`

- [ ] **Step 1: Add top-level navigation to `index.html`**

In `website/python-a/index.html`, inside `<header class="topbar">` after `.market-strip`, add:

```html
        <nav class="main-tabs" aria-label="工作台视图">
          <button class="main-tab active" data-view="research" type="button">股票研究</button>
          <button class="main-tab" data-view="trading" type="button">交易复盘</button>
        </nav>
```

- [ ] **Step 2: Wrap the existing workspace as research view**

Change:

```html
      <main class="workspace">
```

to:

```html
      <main id="researchView" class="workspace view-panel active">
```

After the existing `</main>` for the research workspace, add a new trading main:

```html
      <main id="tradingView" class="trading-workspace view-panel" hidden>
        <section class="panel trading-panel">
          <div class="panel-head">
            <div>
              <h2>交易复盘</h2>
              <p>每日收盘后确认账户、交易和心得</p>
            </div>
            <label class="compact-field">
              <span>复盘日期</span>
              <input id="tradingDate" type="date" />
            </label>
          </div>

          <div class="privacy-note">
            截图解析会将图片发送给外部 AI 视觉接口；原图不会保存到本地项目目录。解析结果需要确认后才会入账。
          </div>

          <div class="trading-grid">
            <section class="trading-card">
              <h3>账户资金</h3>
              <div id="accountSummary" class="metric-grid"></div>
            </section>

            <section class="trading-card">
              <h3>本金流水</h3>
              <form id="capitalFlowForm" class="trading-form">
                <select id="capitalFlowType">
                  <option value="initial">初始本金</option>
                  <option value="deposit">入金</option>
                  <option value="withdraw">出金</option>
                  <option value="adjustment">资金修正</option>
                </select>
                <input id="capitalFlowAmount" type="number" step="0.01" placeholder="金额" />
                <input id="capitalFlowNote" placeholder="说明" />
                <button class="secondary-button" type="submit">保存流水</button>
              </form>
              <div id="capitalFlowList" class="simple-list"></div>
            </section>

            <section class="trading-card">
              <h3>截图解析</h3>
              <form id="accountScreenshotForm" class="upload-form">
                <input id="accountScreenshotInput" type="file" accept="image/*" />
                <button class="secondary-button" type="submit">解析账户截图</button>
              </form>
              <form id="tradesScreenshotForm" class="upload-form">
                <input id="tradesScreenshotInput" type="file" accept="image/*" />
                <button class="secondary-button" type="submit">解析成交截图</button>
              </form>
            </section>

            <section class="trading-card span-2">
              <h3>待确认解析结果</h3>
              <div id="parseDraftList" class="draft-list"></div>
            </section>

            <section class="trading-card span-2">
              <h3>今日交易</h3>
              <form id="manualTradeForm" class="trade-form">
                <input id="tradeStockCode" maxlength="6" placeholder="代码" />
                <input id="tradeStockName" placeholder="名称" />
                <select id="tradeSide">
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                </select>
                <input id="tradeTime" type="datetime-local" />
                <input id="tradePrice" type="number" step="0.001" placeholder="价格" />
                <input id="tradeQuantity" type="number" step="1" placeholder="数量" />
                <input id="tradeAmount" type="number" step="0.01" placeholder="金额" />
                <button class="secondary-button" type="submit">新增交易</button>
              </form>
              <div id="tradeList" class="trade-list"></div>
            </section>

            <section class="trading-card span-2">
              <h3>今日复盘</h3>
              <form id="dailyReviewForm" class="daily-review-form">
                <textarea id="dailySummary" rows="2" placeholder="今日操作总结"></textarea>
                <textarea id="dailyDidWell" rows="2" placeholder="今天做对了什么"></textarea>
                <textarea id="dailyMistake" rows="2" placeholder="今天做错了什么"></textarea>
                <textarea id="dailyPositionReview" rows="2" placeholder="仓位是否合理"></textarea>
                <textarea id="dailyEmotionReview" rows="2" placeholder="情绪是否影响操作"></textarea>
                <textarea id="dailyNextPlan" rows="2" placeholder="明日观察计划"></textarea>
                <textarea id="dailyLesson" rows="3" placeholder="自由心得"></textarea>
                <button class="primary-button" type="submit">保存每日复盘</button>
              </form>
            </section>
          </div>
        </section>
      </main>
```

- [ ] **Step 3: Add CSS for tabs and trading cards**

Append to `website/python-a/styles.css`:

```css
.main-tabs {
  display: flex;
  gap: 8px;
  align-items: center;
}

.main-tab {
  border: 1px solid rgba(31, 41, 55, 0.16);
  background: #ffffff;
  color: #374151;
  border-radius: 8px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}

.main-tab.active {
  background: #111827;
  color: #ffffff;
}

.view-panel[hidden] {
  display: none;
}

.trading-workspace {
  padding: 18px;
}

.trading-panel {
  max-width: 1280px;
  margin: 0 auto;
}

.compact-field {
  display: grid;
  gap: 6px;
  color: #4b5563;
  font-size: 13px;
}

.compact-field input,
.trading-form input,
.trading-form select,
.trade-form input,
.trade-form select,
.daily-review-form textarea,
.upload-form input {
  border: 1px solid #d5dde4;
  border-radius: 8px;
  padding: 9px 10px;
  font: inherit;
  background: #ffffff;
}

.privacy-note {
  margin: 14px 0;
  border: 1px solid #f0c36a;
  background: #fff8e6;
  color: #7a4b00;
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.5;
}

.trading-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.trading-card {
  border: 1px solid #e3e8ee;
  border-radius: 8px;
  padding: 14px;
  background: #ffffff;
}

.trading-card h3 {
  margin: 0 0 12px;
  font-size: 17px;
}

.span-2 {
  grid-column: span 2;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  background: #f7faf9;
  border-radius: 8px;
  padding: 10px;
}

.metric-item span {
  display: block;
  color: #6b7280;
  font-size: 12px;
}

.metric-item strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 18px;
}

.trading-form,
.upload-form,
.trade-form,
.daily-review-form {
  display: grid;
  gap: 10px;
}

.trade-form {
  grid-template-columns: 0.7fr 1fr 0.8fr 1.3fr 0.8fr 0.8fr 0.9fr auto;
  align-items: end;
}

.simple-list,
.draft-list,
.trade-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.list-row {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #fbfcfd;
}

@media (max-width: 900px) {
  .trading-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: span 1;
  }

  .metric-grid,
  .trade-form {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Commit Task 7**

Run:

```powershell
git add website/python-a/index.html website/python-a/styles.css
git commit -m "feat: add python-a trading review layout"
```

---

### Task 8: Frontend Trading Review Behavior

**Files:**
- Modify: `website/python-a/app.js`

- [ ] **Step 1: Extend frontend state**

Near existing `state`, add:

```javascript
const tradingState = {
  activeView: "research",
  date: today(),
  dashboard: null,
  loading: false,
};
```

- [ ] **Step 2: Add trading API helpers**

Add after `requestJson`:

```javascript
async function requestForm(url, formData) {
  const response = await fetch(url, { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok || payload.ok === false || payload.success === false) {
    throw new Error(payload.message || payload.error || "请求失败");
  }
  return payload;
}

async function loadTradingDashboard() {
  const date = $("#tradingDate").value || today();
  tradingState.date = date;
  const payload = await requestJson(`/api/trading/dashboard?date=${encodeURIComponent(date)}`, { cache: "no-store" });
  tradingState.dashboard = payload;
  renderTradingDashboard();
}
```

- [ ] **Step 3: Add trading renderers**

Add after `renderAll`:

```javascript
function renderTradingDashboard() {
  const payload = tradingState.dashboard || {};
  const account = payload.account || {};
  const snapshot = account.snapshot || {};
  const metrics = [
    ["总资产", snapshot.total_assets],
    ["本金", account.principal],
    ["账户收益", snapshot.account_profit],
    ["收益率", typeof snapshot.account_profit_rate === "number" ? `${(snapshot.account_profit_rate * 100).toFixed(2)}%` : "--"],
    ["当日盈亏", snapshot.daily_profit],
    ["浮动盈亏", snapshot.floating_profit],
    ["总市值", snapshot.market_value],
    ["可用资金", snapshot.available_cash],
  ];
  $("#accountSummary").innerHTML = metrics
    .map(([label, value]) => `<div class="metric-item"><span>${label}</span><strong>${value ?? "--"}</strong></div>`)
    .join("");

  $("#capitalFlowList").innerHTML = (account.capital_flows || [])
    .map((flow) => `<div class="list-row">${flow.date} · ${flow.type} · ${flow.amount} · ${flow.note || ""}</div>`)
    .join("") || `<div class="list-row">当日暂无本金流水。</div>`;

  $("#tradeList").innerHTML = (payload.trades || [])
    .map((trade) => `<div class="list-row">${trade.trade_datetime} · ${trade.stock_code || "待补"} ${trade.stock_name} · ${trade.side} · ${trade.price} x ${trade.quantity} · ${trade.amount}</div>`)
    .join("") || `<div class="list-row">当日暂无确认交易。</div>`;

  $("#parseDraftList").innerHTML = (payload.parse_drafts || [])
    .map((draft) => `<div class="list-row"><strong>${draft.type}</strong> · ${draft.trade_date} · ${draft.status}<pre>${JSON.stringify(draft.parsed, null, 2)}</pre></div>`)
    .join("") || `<div class="list-row">暂无待确认解析结果。</div>`;
}

function switchMainView(view) {
  tradingState.activeView = view;
  document.querySelectorAll(".main-tab").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $("#researchView").hidden = view !== "research";
  $("#tradingView").hidden = view !== "trading";
  if (view === "trading") {
    loadTradingDashboard().catch((error) => showToast(error.message));
  }
}
```

- [ ] **Step 4: Add submit handlers**

Add after `saveStockReview`:

```javascript
async function saveCapitalFlow(event) {
  event.preventDefault();
  const payload = {
    date: $("#tradingDate").value || today(),
    type: $("#capitalFlowType").value,
    amount: Number($("#capitalFlowAmount").value),
    note: $("#capitalFlowNote").value.trim(),
  };
  try {
    await requestJson("/api/trading/capital-flows", { method: "POST", body: JSON.stringify(payload) });
    $("#capitalFlowForm").reset();
    await loadTradingDashboard();
    showToast("本金流水已保存");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveManualTrade(event) {
  event.preventDefault();
  const payload = {
    trade_datetime: $("#tradeTime").value ? new Date($("#tradeTime").value).toISOString() : `${$("#tradingDate").value || today()}T15:00:00+08:00`,
    stock_code: $("#tradeStockCode").value.trim(),
    stock_name: $("#tradeStockName").value.trim(),
    side: $("#tradeSide").value,
    price: Number($("#tradePrice").value),
    quantity: Number($("#tradeQuantity").value),
    amount: Number($("#tradeAmount").value),
  };
  try {
    await requestJson("/api/trading/trades", { method: "POST", body: JSON.stringify(payload) });
    $("#manualTradeForm").reset();
    await loadTradingDashboard();
    showToast("交易记录已保存");
  } catch (error) {
    showToast(error.message);
  }
}

async function uploadTradingScreenshot(event, inputId, endpoint) {
  event.preventDefault();
  const file = $(`#${inputId}`).files[0];
  if (!file) {
    showToast("请先选择截图");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("trade_date", $("#tradingDate").value || today());
  try {
    await requestForm(endpoint, formData);
    await loadTradingDashboard();
    showToast("截图解析草稿已生成，请确认后入账");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveDailyReview(event) {
  event.preventDefault();
  const dashboard = tradingState.dashboard || {};
  const payload = {
    date: $("#tradingDate").value || today(),
    snapshot: dashboard.account?.snapshot || {},
    trades: dashboard.trades || [],
    review: {
      summary: $("#dailySummary").value.trim(),
      did_well: $("#dailyDidWell").value.trim(),
      mistake: $("#dailyMistake").value.trim(),
      position_review: $("#dailyPositionReview").value.trim(),
      emotion_review: $("#dailyEmotionReview").value.trim(),
      next_plan: $("#dailyNextPlan").value.trim(),
      lesson: $("#dailyLesson").value.trim(),
    },
  };
  try {
    await requestJson("/api/trading/daily-review", { method: "POST", body: JSON.stringify(payload) });
    showToast("每日交易复盘已写入 Obsidian");
  } catch (error) {
    showToast(error.message);
  }
}
```

- [ ] **Step 5: Bind trading events**

In `bindEvents`, add:

```javascript
  $("#tradingDate").value = today();
  document.querySelectorAll(".main-tab").forEach((button) => {
    button.addEventListener("click", () => switchMainView(button.dataset.view));
  });
  $("#tradingDate").addEventListener("change", () => loadTradingDashboard().catch((error) => showToast(error.message)));
  $("#capitalFlowForm").addEventListener("submit", saveCapitalFlow);
  $("#manualTradeForm").addEventListener("submit", saveManualTrade);
  $("#accountScreenshotForm").addEventListener("submit", (event) =>
    uploadTradingScreenshot(event, "accountScreenshotInput", "/api/trading/parse/account-screenshot"),
  );
  $("#tradesScreenshotForm").addEventListener("submit", (event) =>
    uploadTradingScreenshot(event, "tradesScreenshotInput", "/api/trading/parse/trades-screenshot"),
  );
  $("#dailyReviewForm").addEventListener("submit", saveDailyReview);
```

- [ ] **Step 6: Run server and manually verify tab behavior**

Run:

```powershell
cd website/python-a
python server.py
```

Open:

```text
http://127.0.0.1:5174/
```

Expected:

- Page opens on old stock research view.
- Clicking `交易复盘` shows the trading page.
- Clicking `股票研究` returns to old view.
- Trading date defaults to current date.

- [ ] **Step 7: Commit Task 8**

Run:

```powershell
git add website/python-a/app.js
git commit -m "feat: wire python-a trading review frontend"
```

---

### Task 9: Documentation Updates

**Files:**
- Modify: `website/python-a/README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update `website/python-a/README.md` feature list**

Add bullets under current features:

```markdown
- 交易复盘账本：记录本金流水、账户快照、成交记录和每日复盘。
- 截图解析草稿：支持账户资金截图和历史成交截图 AI 解析，确认后才入账。
- 交易心得沉淀：写入每日复盘、每股长期文件和 `交易心得总纲.md`。
```

- [ ] **Step 2: Update `website/python-a/README.md` API section**

Add:

```markdown
## 交易复盘 API

```text
GET  /api/trading/dashboard?date=2026-06-05
GET  /api/trading/capital-flows
POST /api/trading/capital-flows
GET  /api/trading/account-snapshots
POST /api/trading/account-snapshots
GET  /api/trading/trades?date=2026-06-05
POST /api/trading/trades
POST /api/trading/parse/account-screenshot
POST /api/trading/parse/trades-screenshot
GET  /api/trading/parse-drafts
POST /api/trading/parse-drafts/{id}/confirm
POST /api/trading/parse-drafts/{id}/reject
POST /api/trading/daily-review
POST /api/trading/insights/update
```

截图解析会将图片发送给外部 AI 视觉接口。原图不保存，解析草稿必须确认后才写入账本。
```

- [ ] **Step 3: Update root `AGENTS.md` python-a API list**

In the `python-a` API section, append:

```text
GET    /api/trading/dashboard?date={yyyy-MM-dd}
GET    /api/trading/capital-flows
POST   /api/trading/capital-flows
GET    /api/trading/account-snapshots
POST   /api/trading/account-snapshots
GET    /api/trading/trades?date={yyyy-MM-dd}
POST   /api/trading/trades
POST   /api/trading/parse/account-screenshot
POST   /api/trading/parse/trades-screenshot
GET    /api/trading/parse-drafts
POST   /api/trading/parse-drafts/{id}/confirm
POST   /api/trading/parse-drafts/{id}/reject
POST   /api/trading/daily-review
POST   /api/trading/insights/update
```

- [ ] **Step 4: Commit Task 9**

Run:

```powershell
git add website/python-a/README.md AGENTS.md
git commit -m "docs: document python-a trading review workflow"
```

---

### Task 10: Verification And Final Review

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run all python-a unit tests**

Run:

```powershell
cd website/python-a
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Start python-a**

Run:

```powershell
cd website/python-a
python server.py
```

Expected console:

```text
A股研究台 running at http://127.0.0.1:5174
Obsidian vault root: ...
```

- [ ] **Step 3: Verify old health API**

Run:

```powershell
curl.exe -s http://127.0.0.1:5174/api/health
```

Expected JSON contains:

```json
{
  "ok": true
}
```

- [ ] **Step 4: Verify trading dashboard API**

Run:

```powershell
curl.exe -s "http://127.0.0.1:5174/api/trading/dashboard?date=2026-06-05"
```

Expected JSON contains:

```json
{
  "success": true,
  "date": "2026-06-05"
}
```

- [ ] **Step 5: Verify manual capital flow API**

Run:

```powershell
curl.exe -s -H "Content-Type: application/json" -d "{\"date\":\"2026-06-05\",\"type\":\"initial\",\"amount\":16000,\"note\":\"初始本金\"}" http://127.0.0.1:5174/api/trading/capital-flows
```

Expected JSON contains `"success": true` and a `flow.id` beginning with `cf_20260605_`.

- [ ] **Step 6: Verify manual trade API**

Run:

```powershell
curl.exe -s -H "Content-Type: application/json" -d "{\"trade_datetime\":\"2026-06-04T14:40:20+08:00\",\"stock_code\":\"601991\",\"stock_name\":\"大唐发电\",\"side\":\"buy\",\"price\":8.99,\"quantity\":300,\"amount\":2697}" http://127.0.0.1:5174/api/trading/trades
```

Expected JSON contains `"success": true` and `trade.stock_name` is `大唐发电`.

- [ ] **Step 7: Verify screenshot upload without vision key gives clear error**

Run with any small local image path:

```powershell
curl.exe -s -F "trade_date=2026-06-05" -F "file=@D:\QQ文档\xwechat_files\wxid_keiq1gi9eleh22_a6dd\temp\RWTemp\2026-06\b76f4e15eb58eab1eb24d830d553d3d9.jpg" http://127.0.0.1:5174/api/trading/parse/account-screenshot
```

Expected JSON contains `"success": false` and a message containing `VISION_API_KEY`.

- [ ] **Step 8: Verify frontend manually**

Open:

```text
http://127.0.0.1:5174/
```

Expected:

- Old stock research page is the default view.
- Top tabs show `股票研究` and `交易复盘`.
- Trading review tab loads without console errors.
- Capital flow form saves and refreshes the summary.
- Manual trade form saves and displays the trade.
- Daily review form writes `obsidian-vault/A股AI/每日复盘/{date}-交易复盘.md`.

- [ ] **Step 9: Check git status**

Run:

```powershell
git status --short
```

Expected:

- Only intentional files are modified or untracked.
- Do not stage `deepseek.local.json`, logs, screenshots, `__pycache__`, or generated private outputs.

- [ ] **Step 10: Final commit**

If all verification passes, commit remaining intentional changes:

```powershell
git add website/python-a AGENTS.md
git commit -m "feat: add python-a trading review ledger"
```

## Plan Self-Review

Spec coverage:

- Existing page default and old APIs are preserved in Tasks 6, 7, and 8.
- JSON ledger storage is covered by Tasks 1, 2, and 3.
- Account screenshot and trade screenshot parsing are covered by Tasks 5 and 6.
- Manual confirmation drafts are covered by Task 3 and exposed through Task 6.
- Obsidian daily review, stock file, and insight index are covered by Task 4.
- Frontend trading review workflow is covered by Tasks 7 and 8.
- Documentation is covered by Task 9.
- Verification is covered by Task 10.

Placeholder scan:

- The plan contains concrete file paths, commands, code snippets, and expected results.
- No task depends on an undefined service or route without a previous task defining it.

Type consistency:

- API responses use both `ok` and `success` for compatibility.
- Service file names match imports used in `server.py`.
- Data keys match the design spec: `capital_flows.json`, `account_snapshots.json`, `trades.json`, `parse_drafts.json`, and `交易心得总纲.md`.
