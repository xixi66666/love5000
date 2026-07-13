import unittest

import server


class FakeResearchService:
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
