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
