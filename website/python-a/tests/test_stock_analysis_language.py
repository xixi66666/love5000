"""中文输出约束的回归测试。

被测对象：``server.deepseek_dimension_prompt`` 生成的提示词必须要求中文字段并禁止确定性买卖
指令；``app.js`` 中的专业分析请求必须要求全程中文，不得输出英文标题或英文段落。

隔离：前者只拼接字符串并断言关键字，后者以文本方式读取 app.js，二者都不发网络请求、
不读取 model.properties 或密钥，也不需要浏览器。
"""
from pathlib import Path
import unittest

from server import deepseek_dimension_prompt


class StockAnalysisLanguageTests(unittest.TestCase):
    """分别锁住后端提示词与前端请求里的中文约束，防止模型输出英文或买卖指令。"""
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
