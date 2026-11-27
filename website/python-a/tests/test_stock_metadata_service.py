"""股票元数据服务（services.stock_metadata_service.StockMetadataService）的单元测试。

被测对象：行业、板块、概念元数据的数据源优先级与降级链 —— 先读本地缓存，缓存缺失时走东方财富
板块接口，其次 Tushare（需要 token），两者都失败时才回退调用方传入的 fallback，并用 ``source``
字段如实标注本次数据来自哪个源，避免页面把兜底数据展示成实时数据。

隔离：全部使用手写替身：``FakeTushareClient`` / ``FakeEastmoneyClient`` 返回固定数据，
``BrokenEastmoneyClient`` 与内联 ``BrokenClient`` 模拟网络异常；缓存根指向
``tempfile.TemporaryDirectory``，不联网、不写 data/stock-metadata 真实目录。
"""
import tempfile
import unittest
from pathlib import Path

from services.stock_metadata_service import StockMetadataService


class FakeTushareClient:
    """伪造 Tushare 客户端：stock_basic 返回个股基础信息，ths_member 返回概念成员，其余接口返回空列表。"""
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
    """伪造东方财富板块接口：同时给出行业、地域与概念板块，用来验证服务端的板块筛选规则。"""
    def fetch_boards(self, code):
        return [
            {"BOARD_NAME": "电力设备", "BOARD_RANK": 1, "IS_PRECISE": None},
            {"BOARD_NAME": "电池", "BOARD_RANK": 2, "IS_PRECISE": "0"},
            {"BOARD_NAME": "山东板块", "BOARD_RANK": 4, "IS_PRECISE": "0"},
            {"BOARD_NAME": "储能概念", "BOARD_RANK": 10, "IS_PRECISE": "1"},
            {"BOARD_NAME": "钠离子电池", "BOARD_RANK": 11, "IS_PRECISE": "1"},
        ]


class BrokenEastmoneyClient:
    """模拟板块接口整体不可用，用于触发服务换用下一个数据源。"""
    def fetch_boards(self, code):
        raise RuntimeError("network failed")


class StockMetadataServiceTests(unittest.TestCase):
    """覆盖三条降级路径：东方财富优先、Tushare 兜底并写缓存、两个源都失败时回退 fallback。"""
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
