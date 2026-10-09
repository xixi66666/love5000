import re
import unittest

from fastapi.testclient import TestClient

from main import FRONTEND_DIST_DIR, app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_returns_unified_service_status(self):
        response = self.client.get("/api/health")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual("scrapling-ui", payload["service"])

    def test_unknown_api_path_is_not_swallowed_by_spa_fallback(self):
        response = self.client.get("/api/does-not-exist")

        self.assertEqual(404, response.status_code)

    def test_frontend_index_is_served_when_dist_is_built(self):
        if not (FRONTEND_DIST_DIR / "index.html").is_file():
            self.skipTest("frontend/dist is not built yet")

        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_built_javascript_asset_is_served_with_javascript_mime_type(self):
        index_file = FRONTEND_DIST_DIR / "index.html"
        if not index_file.is_file():
            self.skipTest("frontend/dist is not built yet")

        html = index_file.read_text(encoding="utf-8")
        match = re.search(r'src="(/assets/[^"]+\.js)"', html)
        self.assertIsNotNone(match, "built index.html should reference a JS asset")

        response = self.client.get(match.group(1))

        self.assertEqual(200, response.status_code)
        self.assertIn("javascript", response.headers.get("content-type", ""),
                      "ES module scripts require a JavaScript MIME type (text/plain breaks them)")


if __name__ == "__main__":
    unittest.main()
