"""选号策略及 HTTP 接口验证。"""
import http.client
import importlib.util
import json
import random
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import selection


class SelectionTests(unittest.TestCase):
    def test_real_history_produces_legal_selections(self):
        for game, pool, pick, back_pool, back_pick in (("ssq", 33, 6, 16, 1), ("dlt", 35, 5, 12, 2)):
            for method in selection.METHODS:
                with self.subTest(game=game, method=method):
                    result = selection.generate(game, method, 3, random.Random(123))
                    self.assertEqual(3, len(result["tickets"]))
                    self.assertTrue(result["data_issue"])
                    for ticket in result["tickets"]:
                        for area, maximum, size in (("front", pool, pick), ("back", back_pool, back_pick)):
                            numbers = ticket[area]
                            self.assertEqual(size, len(set(numbers)))
                            self.assertEqual(numbers, sorted(numbers))
                            self.assertTrue(all(1 <= n <= maximum for n in numbers))

    def test_top_and_bottom_frequency_and_overdue(self):
        # 构造 100 期，使前区 1..6 最热，7..12 从未出现。
        draws = [("2026-01-01", i, [{1, 2, 3, 4, 5, 6}, {1}]) for i in range(100)]
        with patch.object(selection, "load_draws", return_value=draws):
            for method in ("hot100", "weighted"):
                self.assertEqual([1, 2, 3, 4, 5, 6], selection.generate("ssq", method, 1, random.Random(1))["tickets"][0]["front"])
            for method in ("cold100", "overdue"):
                ticket = selection.generate("ssq", method, 1, random.Random(1))["tickets"][0]["front"]
                self.assertFalse(set(ticket) & {1, 2, 3, 4, 5, 6})

    def test_ticket_stats_match_numbers(self):
        for game, pick in (("ssq", 6), ("dlt", 5)):
            ticket = selection.generate(game, "random", 1, random.Random(7))["tickets"][0]
            stats = ticket["stats"]
            self.assertEqual(sum(ticket["front"]), stats["sum"])
            self.assertEqual(max(ticket["front"]) - min(ticket["front"]), stats["span"])
            self.assertEqual(pick, sum(stats["zone_parts"]))
            self.assertTrue(0 <= stats["ac"] <= pick * (pick - 1) // 2)
            self.assertTrue(0 <= ticket["repeat"] <= pick)
            self.assertEqual(3, len(stats["zone"].split("|")))

    def test_bad_parameters(self):
        for game, method, count in (("x", "random", 1), ("ssq", "x", 1), ("dlt", "random", 0), ("dlt", "random", 11)):
            with self.assertRaises(ValueError):
                selection.generate(game, method, count)


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 接口测试不需要 pandas，仅替代本机可能缺失的 pandas 依赖。
        with patch.dict(sys.modules, {"pandas": types.ModuleType("pandas")}):
            spec = importlib.util.spec_from_file_location("lottery_test_server", ROOT / "server.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        cls.httpd = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        conn.close()
        return response.status, payload

    def test_success_and_invalid_params(self):
        status, payload = self.request("/api/selection?game=ssq&method=hot100&count=1")
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])
        self.assertEqual(20, len(payload["recent"]))
        self.assertIn("stats", payload["tickets"][0])
        for query in ("game=ssq&method=random&count=11", "game=ssq&method=random&count=1&count=2", "game=unknown&method=random&count=1"):
            status, payload = self.request("/api/selection?" + query)
            self.assertEqual(400, status)
            self.assertFalse(payload["success"])

    def test_recent_endpoint(self):
        status, payload = self.request("/api/recent?game=ssq&count=20")
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])
        self.assertEqual(20, len(payload["draws"]))
        issues = [row["issue"] for row in payload["draws"]]
        self.assertEqual(sorted(issues, reverse=True), issues)
        for row in payload["draws"]:
            self.assertIn("stats", row)
            self.assertIn("repeat", row)
        for query in ("game=unknown", "game=ssq&count=0", "game=ssq&count=51", "count=20"):
            status, payload = self.request("/api/recent?" + query)
            self.assertEqual(400, status)
            self.assertFalse(payload["success"])


if __name__ == "__main__":
    unittest.main()
