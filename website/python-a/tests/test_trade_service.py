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
