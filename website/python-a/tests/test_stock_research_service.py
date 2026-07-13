import unittest

from services.research_provider import ResearchProviderError, success_block
from services.stock_research_service import StockResearchService


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def monotonic(self):
        return self.value


class FakeTencentProvider:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def fetch(self, code):
        self.calls += 1
        if self.error:
            raise self.error
        return success_block(
            "tencent",
            {"pe_ttm": 26.8, "pb": 2.35, "market_cap_yi": 91.2, "float_market_cap_yi": 88.1},
            data_date="2026-07-13",
        )


class FakeEastmoneyProvider:
    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.calls = []

    def _result(self, name, data, data_date="2026-07-11"):
        self.calls.append(name)
        if name in self.failures:
            raise ResearchProviderError("{} failed".format(name), retryable=True)
        return success_block("eastmoney", data, data_date=data_date)

    def fetch_overview(self, code):
        return self._result("overview", {"pe_ttm": 27.1, "pb": 2.4})

    def fetch_fund_flow(self, code):
        return self._result("fund_flow", {"today_main_net": 100.0, "five_day_direction": "净流入"})

    def fetch_margin(self, code):
        return self._result("margin", {"latest_balance": 120000000.0, "balance_change": 20000000.0})

    def fetch_shareholders(self, code):
        return self._result("shareholders", {"holder_count": 32100, "change_ratio": -3.5})

    def fetch_lockups(self, code):
        return self._result("lockups", {"upcoming": []})

    def fetch_reports(self, code, page=1, page_size=10):
        return self._result(
            "reports",
            {
                "items": [
                    {
                        "title": "研报 {}".format(page),
                        "organization": "研究机构",
                        "rating": "增持",
                        "date": "2026-07-10",
                        "url": "https://pdf.dfcfw.com/report.pdf",
                    }
                ],
                "page": page,
                "page_size": page_size,
                "has_more": page < 2,
            },
            data_date="2026-07-10",
        )


class FakeSinaProvider:
    def __init__(self):
        self.calls = 0

    def fetch(self, code):
        self.calls += 1
        return success_block(
            "sina",
            {"today_main_net": 80.0, "five_day_direction": "净流入", "twenty_day_direction": "净流出"},
            data_date="2026-07-11",
        )


class FakeCninfoProvider:
    def __init__(self, primary_fails=False):
        self.primary_fails = primary_fails
        self.calls = []

    def fetch(self, code, page=1, page_size=10):
        self.calls.append(("primary", page, page_size))
        if self.primary_fails:
            raise ResearchProviderError("cninfo failed")
        return success_block(
            "cninfo",
            {"items": [{"title": "公告", "date": "2026-07-11", "url": "https://www.cninfo.com.cn/a"}], "page": page, "page_size": page_size, "has_more": False},
            data_date="2026-07-11",
        )

    def fetch_backup(self, code, page=1, page_size=10):
        self.calls.append(("backup", page, page_size))
        return success_block(
            "szse",
            {"items": [{"title": "备用公告", "date": "2026-07-10", "url": "https://disc.static.szse.cn/a.pdf"}], "page": page, "page_size": page_size, "has_more": False},
            data_date="2026-07-10",
        )


class FakeMetadataService:
    def get_stock_metadata(self, code, fallback=None):
        return {
            "code": code,
            "industry": "电力设备",
            "concepts": ["储能", "钠离子电池"],
            "source": "eastmoney",
        }


def make_service(tencent=None, eastmoney=None, sina=None, cninfo=None, clock=None):
    return StockResearchService(
        tencent_provider=tencent or FakeTencentProvider(),
        eastmoney_provider=eastmoney or FakeEastmoneyProvider(),
        sina_provider=sina or FakeSinaProvider(),
        cninfo_provider=cninfo or FakeCninfoProvider(),
        metadata_service=FakeMetadataService(),
        monotonic=(clock or FakeClock()).monotonic,
    )


class StockResearchServiceTests(unittest.TestCase):
    def test_overview_keeps_valuation_and_metadata_sources_independent(self):
        result = make_service().get_overview("002580")

        self.assertEqual(result["section"], "overview")
        self.assertEqual(result["blocks"]["valuation"]["provider"], "tencent")
        self.assertEqual(result["blocks"]["metadata"]["provider"], "eastmoney")
        self.assertEqual(result["blocks"]["metadata"]["data"]["industry"], "电力设备")

    def test_overview_falls_back_to_eastmoney_and_marks_actual_source(self):
        tencent = FakeTencentProvider(error=ResearchProviderError("tencent failed"))

        result = make_service(tencent=tencent).get_overview("002580")

        valuation = result["blocks"]["valuation"]
        self.assertEqual(valuation["provider"], "eastmoney")
        self.assertTrue(valuation["fallback_used"])

    def test_capital_supports_mixed_sources_and_partial_failure(self):
        eastmoney = FakeEastmoneyProvider(failures={"fund_flow", "shareholders"})

        result = make_service(eastmoney=eastmoney).get_capital("002580")

        self.assertEqual(result["blocks"]["fund_flow"]["provider"], "sina")
        self.assertTrue(result["blocks"]["fund_flow"]["fallback_used"])
        self.assertEqual(result["blocks"]["margin"]["provider"], "eastmoney")
        self.assertFalse(result["blocks"]["shareholders"]["success"])
        self.assertIsNone(result["blocks"]["shareholders"]["provider"])
        self.assertTrue(result["success"])

    def test_cache_hit_and_force_refresh(self):
        clock = FakeClock()
        tencent = FakeTencentProvider()
        service = make_service(tencent=tencent, clock=clock)

        service.get_overview("002580")
        service.get_overview("002580")
        service.get_overview("002580", force=True)

        self.assertEqual(tencent.calls, 2)

    def test_events_support_independent_kind_pagination_and_announcement_fallback(self):
        cninfo = FakeCninfoProvider(primary_fails=True)
        service = make_service(cninfo=cninfo)

        reports = service.get_events("002580", kind="reports", page=2, page_size=10)
        announcements = service.get_events("002580", kind="announcements", page=1, page_size=10)

        self.assertEqual(reports["blocks"]["reports"]["data"]["page"], 2)
        self.assertNotIn("announcements", reports["blocks"])
        self.assertEqual(announcements["blocks"]["announcements"]["provider"], "szse")
        self.assertTrue(announcements["blocks"]["announcements"]["fallback_used"])

    def test_build_snapshot_is_compact_and_preserves_sources(self):
        service = make_service()

        snapshot = service.build_snapshot("002580", load_missing=True)

        self.assertEqual(snapshot["code"], "002580")
        self.assertEqual(snapshot["overview"]["valuation"]["provider"], "tencent")
        self.assertEqual(snapshot["capital"]["fund_flow"]["provider"], "eastmoney")
        self.assertLessEqual(len(snapshot["events"]["reports"]["items"]), 5)
        self.assertLessEqual(len(snapshot["events"]["announcements"]["items"]), 5)

    def test_invalid_events_arguments_are_rejected(self):
        service = make_service()

        with self.assertRaises(ValueError):
            service.get_events("002580", kind="unknown")
        with self.assertRaises(ValueError):
            service.get_events("002580", page=0)
        with self.assertRaises(ValueError):
            service.get_events("002580", page_size=21)


if __name__ == "__main__":
    unittest.main()
