from pathlib import Path
import unittest

from server import deepseek_dimension_prompt


class StockAnalysisLanguageTests(unittest.TestCase):
    def test_deepseek_dimension_prompt_requires_chinese_fields(self):
        messages = deepseek_dimension_prompt(
            {"code": "601991", "name": "大唐发电"},
            {"analysisFocus": "综合复盘"},
        )
        combined = "\n".join(message["content"] for message in messages)

        self.assertIn("每个字段使用中文", combined)
        self.assertIn("不输出确定性买卖指令", combined)

    def test_professional_agent_request_requires_chinese_report(self):
        app_js = Path(__file__).resolve().parents[1] / "app.js"
        source = app_js.read_text(encoding="utf-8")

        self.assertIn("全程使用中文", source)
        self.assertIn("不要输出英文标题", source)
        self.assertIn("不要输出英文段落", source)


if __name__ == "__main__":
    unittest.main()
