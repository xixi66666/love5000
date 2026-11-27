"""股票名称到代码匹配服务（services.stock_match_service.StockMatchService）的单元测试。

被测对象：``match_name`` 的匹配结果（唯一命中 / 未命中）与 ``confirm_mapping`` 手工确认后
能否持久化并影响后续匹配。

隔离：每个用例通过 ``make_service`` 在 ``tempfile.TemporaryDirectory`` 上创建独立的 JsonStore，
三只内置股票以 seed_rows 注入，不读取真实自选股文件、不请求行情或搜索接口。
"""
import tempfile
import unittest
from pathlib import Path

from services.stock_match_service import StockMatchService
from services.storage_service import JsonStore


class StockMatchServiceTests(unittest.TestCase):
    """覆盖三种结果：名称唯一命中、查不到对应股票、以及人工确认映射后再次匹配。"""
    def make_service(self):
        """在独立临时目录上装配 StockMatchService，并注入三只内置股票作为匹配语料。"""
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
