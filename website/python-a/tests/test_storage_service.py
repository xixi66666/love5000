"""JSON 存储层（services.storage_service）的单元测试。

被测对象：``JsonStore`` 的读取、写入、追加与损坏文件处理，以及 ``filter_by_date`` 的日期过滤
和 ``new_id`` 的编号格式。

隔离：所有用例在 ``tempfile.TemporaryDirectory`` 内读写，用完即销毁；文件名带嵌套目录时也只
落在临时根下，不接触 obsidian-vault/A股AI 里的真实交易数据。
"""
import tempfile
import unittest
from pathlib import Path

from services.storage_service import JsonStore, filter_by_date, new_id


class JsonStoreTests(unittest.TestCase):
    """覆盖存储层的五个分支：读缺失文件、写嵌套路径、损坏文件备份、日期过滤、编号格式。"""
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
