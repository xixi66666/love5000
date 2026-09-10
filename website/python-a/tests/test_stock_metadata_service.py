import tempfile
import unittest
from pathlib import Path

from services.stock_metadata_service import StockMetadataService


class FakeTushareClient:
    def __init__(self):
        self.calls = []

    def query(self, api_name, params=None, fields=""):
        self.calls.append((api_name, params or {}, fields))
        if api_name == "stock_basic":
            return [{"ts_code": "002580.SZ", "name": "圣阳股份", "industry": "电池"}]
        if api_name == "ths_member":
            return [
                {"ts_code": "002580.SZ", "name": "储能", "con_name": "圣阳股份"},
                {"ts_code": "002580.SZ", "name": "钠离子电池", "con_name": "圣阳股份"},
            ]
        return []


class FakeEastmoneyClient:
    def fetch_boards(self, code):
        return [
            {"BOARD_NAME": "电力设备", "BOARD_RANK": 1, "IS_PRECISE": None},
            {"BOARD_NAME": "电池", "BOARD_RANK": 2, "IS_PRECISE": "0"},
            {"BOARD_NAME": "山东板块", "BOARD_RANK": 4, "IS_PRECISE": "0"},
            {"BOARD_NAME": "储能概念", "BOARD_RANK": 10, "IS_PRECISE": "1"},
            {"BOARD_NAME": "钠离子电池", "BOARD_RANK": 11, "IS_PRECISE": "1"},
        ]


class BrokenEastmoneyClient:
    def fetch_boards(self, code):
        raise RuntimeError("network failed")


class StockMetadataServiceTests(unittest.TestCase):
    def test_get_stock_metadata_prefers_eastmoney_without_tushare_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = StockMetadataService(
                Path(temp_dir),
                eastmoney_client=FakeEastmoneyClient(),
                client=None,
            )

            metadata = service.get_stock_metadata("002580", fallback={"name": "圣阳股份"})

            self.assertEqual(metadata["industry"], "电力设备")
            self.assertEqual(metadata["concepts"], ["电池", "储能概念", "钠离子电池"])
            self.assertEqual(metadata["source"], "eastmoney")

    def test_get_stock_metadata_uses_tushare_and_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakeTushareClient()
            service = StockMetadataService(
                Path(temp_dir),
                client=client,
                eastmoney_client=BrokenEastmoneyClient(),
            )

            metadata = service.get_stock_metadata("002580")

            self.assertEqual(metadata["industry"], "电池")
            self.assertEqual(metadata["concepts"], ["储能", "钠离子电池"])
            self.assertEqual(metadata["source"], "tushare")
            self.assertTrue((Path(temp_dir) / "stock-metadata" / "002580.json").exists())

    def test_get_stock_metadata_falls_back_to_watchlist_meta_when_source_fails(self):
        class BrokenClient:
            def query(self, api_name, params=None, fields=""):
                raise RuntimeError("network failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = StockMetadataService(
                Path(temp_dir),
                client=BrokenClient(),
                eastmoney_client=BrokenEastmoneyClient(),
            )

            metadata = service.get_stock_metadata(
                "002580",
                fallback={"name": "圣阳股份", "industry": "待映射", "board": "A股"},
            )

            self.assertEqual(metadata["industry"], "待映射")
            self.assertEqual(metadata["concepts"], [])
            self.assertEqual(metadata["source"], "fallback")


if __name__ == "__main__":
    unittest.main()
