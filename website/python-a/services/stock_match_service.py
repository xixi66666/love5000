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
        candidates = self._all_candidates()
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

    def _all_candidates(self) -> List[Dict[str, Any]]:
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
