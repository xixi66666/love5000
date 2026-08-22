import unittest
from unittest import mock

from services.cninfo_announcement_provider import CninfoAnnouncementProvider
from services.eastmoney_research_provider import EastmoneyResearchProvider
from services.research_provider import (
    EastmoneyRateLimiter,
    ResearchProviderError,
    UrlLibHttpClient,
    failure_block,
    is_safe_external_url,
    success_block,
    validate_stock_code,
)
from services.sina_fund_flow_provider import SinaFundFlowProvider
from services.tencent_quote_provider import TencentQuoteProvider, market_prefix


class FakeTextClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def get_text(self, url, headers=None, encoding="utf-8", timeout=15):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "encoding": encoding,
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        return self.payload


class FakeJsonClient:
    def __init__(self, get_payloads=None, post_payloads=None, error=None):
        self.get_payloads = list(get_payloads or [])
        self.post_payloads = list(post_payloads or [])
        self.error = error
        self.calls = []

    def get_json(self, url, params=None, headers=None, timeout=15):
        self.calls.append(("get", url, params or {}))
        if self.error:
            raise self.error
        if not self.get_payloads:
            raise AssertionError("missing fake GET payload")
        return self.get_payloads.pop(0)

    def post_form_json(self, url, data=None, headers=None, timeout=15):
        self.calls.append(("post_form", url, data or {}))
        if self.error:
            raise self.error
        if not self.post_payloads:
            raise AssertionError("missing fake POST payload")
        return self.post_payloads.pop(0)

    def post_json(self, url, data=None, headers=None, timeout=15):
        self.calls.append(("post_json", url, data or {}))
        if self.error:
            raise self.error
        if not self.post_payloads:
            raise AssertionError("missing fake POST payload")
        return self.post_payloads.pop(0)


class FakeClock:
    def __init__(self):
        self.value = 10.0
        self.sleeps = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


def tencent_payload(values, prefix="sz", code="002580"):
    return 'v_{}{}="{}";'.format(prefix, code, "~".join(values))


class ResearchProviderContractTests(unittest.TestCase):
    def test_validate_stock_code_accepts_six_digits_only(self):
        self.assertEqual(validate_stock_code("002580"), "002580")
        for value in ("", "2580", "SH600519", "600519;drop"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_stock_code(value)

    def test_source_blocks_preserve_actual_provider(self):
        success = success_block("sina", {"net_inflow": 12.5}, data_date="2026-07-11", fallback_used=True)
        failure = failure_block("融资融券数据暂不可用", retryable=True)

        self.assertTrue(success["success"])
        self.assertEqual(success["provider"], "sina")
        self.assertTrue(success["fallback_used"])
        self.assertFalse(failure["success"])
        self.assertIsNone(failure["provider"])

    def test_safe_external_url_requires_https_and_known_domain(self):
        allowed = {"data.eastmoney.com", "www.cninfo.com.cn"}

        self.assertTrue(is_safe_external_url("https://data.eastmoney.com/report.pdf", allowed))
        self.assertFalse(is_safe_external_url("http://data.eastmoney.com/report.pdf", allowed))
        self.assertFalse(is_safe_external_url("https://evil.example/report.pdf", allowed))
        self.assertFalse(is_safe_external_url("javascript:alert(1)", allowed))

    @mock.patch("services.research_provider.urllib.request.urlopen")
    def test_url_lib_client_supports_json_get_and_form_post(self, urlopen):
        urlopen.side_effect = [
            FakeHttpResponse(b'{"success": true}'),
            FakeHttpResponse(b'{"items": [1]}'),
        ]
        client = UrlLibHttpClient()

        get_result = client.get_json("https://example.com/api", params={"code": "002580"})
        post_result = client.post_form_json("https://example.com/query", data={"page": "1"})

        self.assertTrue(get_result["success"])
        self.assertEqual(post_result["items"], [1])
        self.assertIn("code=002580", urlopen.call_args_list[0].args[0].full_url)
        self.assertEqual(urlopen.call_args_list[1].args[0].get_method(), "POST")


class TencentQuoteProviderTests(unittest.TestCase):
    def test_market_prefix_supports_a_share_markets(self):
        self.assertEqual(market_prefix("600519"), "sh")
        self.assertEqual(market_prefix("002580"), "sz")
        self.assertEqual(market_prefix("832000"), "bj")

    def test_fetch_parses_overview_fields_and_units(self):
        values = [""] * 88
        values[1] = "圣阳股份"
        values[3] = "34.17"
        values[30] = "20260713143000"
        values[38] = "12.40"
        values[39] = "26.80"
        values[43] = "5.30"
        values[44] = "91.20"
        values[45] = "88.10"
        values[46] = "2.35"
        values[47] = "37.59"
        values[48] = "30.75"
        values[49] = "1.42"
        client = FakeTextClient(tencent_payload(values))

        result = TencentQuoteProvider(client).fetch("002580")

        self.assertEqual(result["provider"], "tencent")
        self.assertEqual(result["data_date"], "2026-07-13")
        self.assertEqual(result["data"]["price"], 34.17)
        self.assertEqual(result["data"]["pe_ttm"], 26.8)
        self.assertEqual(result["data"]["pb"], 2.35)
        self.assertEqual(result["data"]["market_cap_yi"], 91.2)
        self.assertEqual(result["data"]["float_market_cap_yi"], 88.1)
        self.assertEqual(result["data"]["turnover_rate"], 12.4)
        self.assertEqual(result["data"]["volume_ratio"], 1.42)
        self.assertEqual(client.calls[0]["encoding"], "gbk")
        self.assertIn("sz002580", client.calls[0]["url"])

    def test_fetch_uses_none_for_missing_values(self):
        values = [""] * 88
        values[1] = "圣阳股份"
        values[3] = "34.17"
        client = FakeTextClient(tencent_payload(values))

        result = TencentQuoteProvider(client).fetch("002580")

        self.assertIsNone(result["data"]["pe_ttm"])
        self.assertIsNone(result["data"]["pb"])
        self.assertIsNone(result["data_date"])

    def test_fetch_wraps_network_errors(self):
        client = FakeTextClient(error=OSError("network down"))

        with self.assertRaises(ResearchProviderError) as context:
            TencentQuoteProvider(client).fetch("002580")

        self.assertTrue(context.exception.retryable)


class EastmoneyRateLimiterTests(unittest.TestCase):
    def test_wait_serializes_calls_with_minimum_interval(self):
        clock = FakeClock()
        limiter = EastmoneyRateLimiter(min_interval=1.0, monotonic=clock.monotonic, sleep=clock.sleep)

        with limiter.slot():
            pass
        clock.value += 0.25
        with limiter.slot():
            pass

        self.assertEqual(clock.sleeps, [0.75])


class EastmoneyResearchProviderTests(unittest.TestCase):
    def test_fetch_overview_normalizes_scaled_fields(self):
        client = FakeJsonClient(
            get_payloads=[
                {
                    "data": {
                        "f58": "圣阳股份",
                        "f43": 3417,
                        "f9": 2680,
                        "f23": 235,
                        "f20": 9120000000,
                        "f21": 8810000000,
                        "f10": 142,
                        "f171": 530,
                        "f51": 3759,
                        "f52": 3075,
                        "f124": 1783938600,
                    }
                }
            ]
        )

        result = EastmoneyResearchProvider(client).fetch_overview("002580")

        self.assertEqual(result["provider"], "eastmoney")
        self.assertEqual(result["data"]["price"], 34.17)
        self.assertEqual(result["data"]["pe_ttm"], 26.8)
        self.assertEqual(result["data"]["pb"], 2.35)
        self.assertEqual(result["data"]["market_cap_yi"], 91.2)
        self.assertEqual(result["data"]["limit_up"], 37.59)

    def test_fetch_fund_flow_summarizes_recent_periods(self):
        rows = [
            "2026-07-09,100,0,0,0,0",
            "2026-07-10,-50,0,0,0,0",
            "2026-07-11,200,0,0,0,0",
        ]
        client = FakeJsonClient(get_payloads=[{"data": {"klines": rows}}])

        result = EastmoneyResearchProvider(client).fetch_fund_flow("002580")

        self.assertEqual(result["data_date"], "2026-07-11")
        self.assertEqual(result["data"]["today_main_net"], 200.0)
        self.assertEqual(result["data"]["five_day_net"], 250.0)
        self.assertEqual(result["data"]["twenty_day_direction"], "净流入")

    def test_fetch_margin_shareholders_and_lockups(self):
        client = FakeJsonClient(
            get_payloads=[
                {"result": {"data": [{"DATE": "2026-07-11", "RZYE": 120000000, "RZRQYE": 121000000}, {"DATE": "2026-07-10", "RZYE": 100000000}]}},
                {"result": {"data": [{"END_DATE": "2026-06-30", "HOLDER_NUM": 32100, "HOLDER_NUM_RATIO": -3.5, "AVG_FREE_SHARES": 8000}]}},
                {"result": {"data": [{"FREE_DATE": "2026-08-01", "FREE_SHARES_TYPE": "定向增发", "FREE_SHARES": 500, "ABLE_FREE_SHARES": 450, "FREE_RATIO": 0.012}]}},
            ]
        )
        provider = EastmoneyResearchProvider(client)

        margin = provider.fetch_margin("002580")
        holders = provider.fetch_shareholders("002580")
        lockups = provider.fetch_lockups("002580", today="2026-07-13")

        self.assertEqual(margin["data"]["latest_balance"], 120000000.0)
        self.assertEqual(margin["data"]["balance_change"], 20000000.0)
        self.assertEqual(holders["data"]["holder_count"], 32100)
        self.assertEqual(holders["data"]["change_ratio"], -3.5)
        self.assertEqual(lockups["data"]["upcoming"][0]["able_shares"], 450.0)

    def test_fetch_reports_returns_safe_pdf_links(self):
        client = FakeJsonClient(
            get_payloads=[
                {
                    "data": [
                        {
                            "title": "储能业务跟踪",
                            "publishDate": "2026-07-10 00:00:00",
                            "orgSName": "研究机构",
                            "infoCode": "ABC123",
                            "emRatingName": "增持",
                            "predictThisYearEps": 1.2,
                        }
                    ],
                    "TotalPage": 1,
                }
            ]
        )

        result = EastmoneyResearchProvider(client).fetch_reports("002580", page=1, page_size=10)

        report = result["data"]["items"][0]
        self.assertEqual(report["organization"], "研究机构")
        self.assertEqual(report["rating"], "增持")
        self.assertEqual(report["eps_forecast"], 1.2)
        self.assertEqual(report["url"], "https://pdf.dfcfw.com/pdf/H3_ABC123_1.pdf")


class SinaFundFlowProviderTests(unittest.TestCase):
    def test_fetch_parses_json_text_and_marks_sina(self):
        payload = '[{"opendate":"2026-07-11","trade":"34.17","netamount":"1200000","turnover":"50000000"},{"opendate":"2026-07-10","trade":"33.50","netamount":"-200000","turnover":"40000000"}]'
        client = FakeTextClient(payload)

        result = SinaFundFlowProvider(client).fetch("002580")

        self.assertEqual(result["provider"], "sina")
        self.assertEqual(result["data"]["today_main_net"], 1200000.0)
        self.assertEqual(result["data"]["five_day_net"], 1000000.0)


class CninfoAnnouncementProviderTests(unittest.TestCase):
    def test_fetch_maps_titles_dates_and_safe_links(self):
        client = FakeJsonClient(
            get_payloads=[{"stockList": [{"code": "002580", "orgId": "gssz0002580"}]}],
            post_payloads=[
                {
                    "announcements": [
                        {
                            "announcementTitle": "关于年度报告的公告",
                            "announcementTypeName": "年度报告",
                            "announcementTime": 1783728000000,
                            "announcementId": "123456",
                        }
                    ],
                    "totalAnnouncement": 1,
                }
            ],
        )

        result = CninfoAnnouncementProvider(client).fetch("002580", page=1, page_size=10)

        announcement = result["data"]["items"][0]
        self.assertEqual(result["provider"], "cninfo")
        self.assertEqual(announcement["type"], "年度报告")
        self.assertEqual(announcement["date"], "2026-07-11")
        self.assertTrue(announcement["url"].startswith("https://www.cninfo.com.cn/"))

    def test_fetch_backup_uses_szse_for_shenzhen_stock(self):
        client = FakeJsonClient(
            post_payloads=[
                {
                    "data": [
                        {
                            "title": "半年度业绩预告",
                            "publishTime": "2026-07-12 09:00:00",
                            "attachPath": "/disc/disk03/finalpage/notice.pdf",
                        }
                    ]
                }
            ]
        )

        result = CninfoAnnouncementProvider(client).fetch_backup("002580", page=1, page_size=10)

        self.assertEqual(result["provider"], "szse")
        self.assertEqual(result["data"]["items"][0]["date"], "2026-07-12")
        self.assertTrue(result["data"]["items"][0]["url"].startswith("https://disc.static.szse.cn/"))



if __name__ == "__main__":
    unittest.main()
