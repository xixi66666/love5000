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
