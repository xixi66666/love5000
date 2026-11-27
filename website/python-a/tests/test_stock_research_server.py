"""server 模块中研究数据路由与 AI 上下文的单元测试。

被测对象：``server.parse_research_route`` 的路径解析、``server.get_research_response`` 的
查询参数映射（force、kind、分页）与非法参数拒绝，以及 ``deepseek_dimension_prompt``
是否把研究快照带进提示词。

隔离：``FakeResearchService`` 是纯内存替身，记录调用参数并返回固定结构；所有用例都不经过
HTTP 处理循环、不请求任何外部行情接口，也不读取模型配置。
"""
import unittest

import server


class FakeResearchService:
    """按分区返回固定结构并记录调用参数的替身，用来验证路由层传下去的参数是否正确。"""
    def __init__(self):
        self.calls = []

    def get_overview(self, code, force=False):
        self.calls.append(("overview", code, force))
        return {"success": True, "section": "overview", "code": code, "blocks": {}}

    def get_capital(self, code, force=False):
        self.calls.append(("capital", code, force))
        return {"success": True, "section": "capital", "code": code, "blocks": {}}

    def get_events(self, code, kind="all", page=1, page_size=10, force=False):
        self.calls.append(("events", code, kind, page, page_size, force))
        return {"success": True, "section": "events", "code": code, "blocks": {}}

    def build_snapshot(self, code, load_missing=True):
        return {"code": code, "overview": {"valuation": {"provider": "tencent", "pe_ttm": 26.8}}}


class ResearchRouteTests(unittest.TestCase):
    """覆盖路径解析、查询参数映射，以及分页非数字和股票代码格式错误时抛 ValueError。"""
    def test_parse_research_route(self):
        self.assertEqual(
            server.parse_research_route("/api/stocks/002580/research/events"),
            ("002580", "events"),
        )
        self.assertIsNone(server.parse_research_route("/api/stock"))

    def test_get_research_response_maps_force_and_event_pagination(self):
        service = FakeResearchService()

        result = server.get_research_response(
            "/api/stocks/002580/research/events",
            "kind=reports&page=2&page_size=20&force=1",
            service=service,
        )

        self.assertTrue(result["success"])
        self.assertEqual(service.calls, [("events", "002580", "reports", 2, 20, True)])

    def test_get_research_response_rejects_invalid_query(self):
        service = FakeResearchService()

        with self.assertRaises(ValueError):
            server.get_research_response(
                "/api/stocks/002580/research/events",
                "page=zero",
                service=service,
            )
        with self.assertRaises(ValueError):
            server.get_research_response(
                "/api/stocks/ABC/research/overview",
                "",
                service=service,
            )


class ResearchAiContextTests(unittest.TestCase):
    """断言研究快照被序列化进用户消息，AI 才能看到真实数据而不是凭名称猜测。"""
    def test_deepseek_prompt_contains_research_snapshot(self):
        snapshot = {
            "code": "002580",
            "overview": {"valuation": {"provider": "tencent", "pe_ttm": 26.8}},
        }

        messages = server.deepseek_dimension_prompt(
            {"code": "002580", "name": "圣阳股份"},
            {"analysis_focus": "综合复盘"},
            snapshot,
        )

        self.assertIn('"research_snapshot"', messages[1]["content"])
        self.assertIn('"provider": "tencent"', messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
