import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services.storage_service import JsonStore
from services.trade_service import DRAFTS_FILE, TradeService


class TradeServiceTests(unittest.TestCase):
    def make_service(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        return TradeService(JsonStore(Path(self.temp_dir.name)))

    def sample_trade(self):
        return {
            "stock_code": "601991",
            "stock_name": "大唐发电",
            "side": "buy",
            "trade_datetime": "2026-06-04T14:40:20+08:00",
            "price": 8.99,
            "quantity": 300,
            "amount": 2697,
        }

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

    def test_confirm_trade_draft_twice_is_idempotent(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        payload = {"trades": [self.sample_trade()]}

        first = service.confirm_draft(draft["id"], payload)
        second = service.confirm_draft(draft["id"], payload)

        self.assertEqual(len(service.list_trades()), 1)
        self.assertEqual(second["draft"]["status"], "confirmed")
        self.assertEqual([trade["id"] for trade in second["created_trades"]], [trade["id"] for trade in first["created_trades"]])
        self.assertEqual(service.list_trades()[0]["source"], "ai_parse")

    def test_confirm_trade_draft_validates_all_trades_before_writing(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        payload = {
            "trades": [
                self.sample_trade(),
                {
                    "stock_code": "600000",
                    "side": "buy",
                    "trade_datetime": "2026-06-04T14:41:00+08:00",
                    "price": 10.0,
                    "quantity": 100,
                    "amount": 1000,
                },
            ]
        }

        with self.assertRaises(ValueError):
            service.confirm_draft(draft["id"], payload)

        self.assertEqual(service.list_trades(), [])
        self.assertEqual(service.list_parse_drafts()[0]["status"], "pending")

        payload["trades"][1]["stock_name"] = "浦发银行"
        result = service.confirm_draft(draft["id"], payload)

        self.assertEqual(len(result["created_trades"]), 2)
        self.assertEqual(len(service.list_trades()), 2)

    def test_confirm_trade_draft_retry_after_draft_save_failure_does_not_duplicate(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        payload = {"trades": [self.sample_trade()]}
        original_write_list = service.store.write_list
        draft_write_count = {"value": 0}

        def fail_second_draft_write(relative_path, rows):
            if relative_path == DRAFTS_FILE:
                draft_write_count["value"] += 1
                if draft_write_count["value"] == 2:
                    raise OSError("simulated draft save failure")
            return original_write_list(relative_path, rows)

        with mock.patch.object(service.store, "write_list", side_effect=fail_second_draft_write):
            with self.assertRaises(OSError):
                service.confirm_draft(draft["id"], payload)

        self.assertEqual(len(service.list_trades()), 1)
        self.assertEqual(service.list_parse_drafts()[0]["status"], "confirming")

        result = service.confirm_draft(draft["id"], payload)

        self.assertEqual(result["draft"]["status"], "confirmed")
        self.assertEqual(len(result["created_trades"]), 1)
        self.assertEqual(len(service.list_trades()), 1)

    def test_confirm_legacy_confirmed_draft_does_not_add_trades(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        drafts = service.store.read_list(DRAFTS_FILE)
        drafts[0]["status"] = "confirmed"
        drafts[0]["confirmed_at"] = "2026-06-05T15:00:00+08:00"
        service.store.write_list(DRAFTS_FILE, drafts)

        result = service.confirm_draft(draft["id"], {"trades": [self.sample_trade()]})

        self.assertEqual(service.list_trades(), [])
        self.assertEqual(result["draft"]["status"], "confirmed")
        self.assertEqual(result["created_trades"], [])

    def test_confirm_legacy_pending_draft_without_status(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        drafts = service.store.read_list(DRAFTS_FILE)
        drafts[0].pop("status")
        service.store.write_list(DRAFTS_FILE, drafts)

        result = service.confirm_draft(draft["id"], {"trades": [self.sample_trade()]})

        self.assertEqual(result["draft"]["status"], "confirmed")
        self.assertEqual(len(service.list_trades()), 1)

    def test_confirm_rejected_draft_does_not_add_trades(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        service.reject_draft(draft["id"])

        with self.assertRaises(ValueError):
            service.confirm_draft(draft["id"], {"trades": [self.sample_trade()]})

        self.assertEqual(service.list_trades(), [])
        self.assertEqual(service.list_parse_drafts()[0]["status"], "rejected")

    def test_reject_confirmed_draft_keeps_confirmed_status(self):
        service = self.make_service()
        draft = service.create_parse_draft("trades_screenshot", "2026-06-05", {"trades": []}, [])
        service.confirm_draft(draft["id"], {"trades": [self.sample_trade()]})

        with self.assertRaises(ValueError):
            service.reject_draft(draft["id"])

        self.assertEqual(service.list_parse_drafts()[0]["status"], "confirmed")

    def test_reject_draft_twice_keeps_rejected_status(self):
        service = self.make_service()
        draft = service.create_parse_draft("account_screenshot", "2026-06-05", {"total_assets": 15909.86}, [])

        service.reject_draft(draft["id"])
        rejected = service.reject_draft(draft["id"])

        self.assertEqual(rejected["status"], "rejected")

    def test_reject_draft_marks_status(self):
        service = self.make_service()
        draft = service.create_parse_draft("account_screenshot", "2026-06-05", {"total_assets": 15909.86}, [])

        rejected = service.reject_draft(draft["id"])

        self.assertEqual(rejected["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
