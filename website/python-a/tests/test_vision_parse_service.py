import unittest

from services.vision_parse_service import VisionParseService


class VisionParseServiceTests(unittest.TestCase):
    def test_parse_without_api_key_raises_clear_error(self):
        service = VisionParseService(api_key="", api_base="https://example.invalid/v1", model="vision-test")

        with self.assertRaises(ValueError) as context:
            service.parse_account_screenshot(b"fake-image", "image/jpeg")

        self.assertIn("VISION_API_KEY", str(context.exception))

    def test_build_account_prompt_names_required_fields(self):
        service = VisionParseService(api_key="key", api_base="https://example.invalid/v1", model="vision-test")

        prompt = service.account_prompt()

        self.assertIn("总资产", prompt)
        self.assertIn("持仓", prompt)
        self.assertIn("严格 JSON", prompt)

    def test_build_trades_prompt_names_required_fields(self):
        service = VisionParseService(api_key="key", api_base="https://example.invalid/v1", model="vision-test")

        prompt = service.trades_prompt()

        self.assertIn("成交时间", prompt)
        self.assertIn("成交价格", prompt)
        self.assertIn("股票代码缺失", prompt)


if __name__ == "__main__":
    unittest.main()
