"""视觉截图解析服务（services.vision_parse_service.VisionParseService）的单元测试。

被测对象：缺少 ``vision.api-key`` 时的报错语义（必须提示配置项名而不是抛裸异常），以及两个
提示词是否点名了必须解析出的字段。

隔离：``api_base`` 指向不可解析的 example.invalid，且只调用不触网的路径：缺 key 时在发请求前
就报错，提示词用例只取字符串；不读取 model.properties、不调用真实视觉模型。
"""
import unittest

from services.vision_parse_service import VisionParseService


class VisionParseServiceTests(unittest.TestCase):
    """覆盖缺密钥的报错文案与两个提示词的关键字段，防止模型返回缺列的结构化结果。"""
    def test_parse_without_api_key_raises_clear_error(self):
        service = VisionParseService(api_key="", api_base="https://example.invalid/v1", model="vision-test")

        with self.assertRaises(ValueError) as context:
            service.parse_account_screenshot(b"fake-image", "image/jpeg")

        self.assertIn("vision.api-key", str(context.exception))

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
