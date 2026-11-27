"""账户资金流水与账户快照服务（services.account_service.AccountService）的单元测试。

被测对象：``AccountService`` 的本金累计、账户快照收益换算和仪表盘取数；存储层用真实的
``services.storage_service.JsonStore``，因此顺带覆盖了 JSON 读写路径。

隔离：每个用例通过 ``make_service`` 新建一个 ``tempfile.TemporaryDirectory`` 作为存储根，
``tearDown`` 统一清理，不触碰 obsidian-vault/A股AI 下的真实数据，也不发网络请求。
"""
import tempfile
import unittest
from pathlib import Path

from services.account_service import AccountService
from services.storage_service import JsonStore


class AccountServiceTests(unittest.TestCase):
    """覆盖三条业务分支：本金按流水类型累计、快照收益与收益率换算、按交易日取最新快照。"""
    def make_service(self):
        """在独立临时目录上装配 AccountService；temp_dir 留给 tearDown 统一清理。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        store = JsonStore(Path(self.temp_dir.name))
        return AccountService(store)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_capital_flow_calculates_principal(self):
        service = self.make_service()

        # 本金按流水类型累计：initial / deposit 为入金，withdraw 记负，adjustment 允许负数修正。
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

        # 账户收益 = 总资产 - 本金；收益率以本金为分母，四舍五入到四位小数。
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
