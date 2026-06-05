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
