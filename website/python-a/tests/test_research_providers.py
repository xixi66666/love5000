import unittest

from services.research_provider import (
    ResearchProviderError,
    failure_block,
    is_safe_external_url,
    success_block,
    validate_stock_code,
)
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


if __name__ == "__main__":
    unittest.main()
