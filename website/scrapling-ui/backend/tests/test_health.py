"""``/api/health``、``/api/**`` 404 与 dist 静态托管的行为测试。

覆盖分支：

- ``GET /api/health`` 返回 200、``success=true`` 与稳定的 ``service=scrapling-ui``
  （``website`` 首页健康巡检依赖这三项）。
- 未匹配的 ``/api/does-not-exist`` 返回 404，而不是被 SPA fallback 吞成 200 HTML。
- ``frontend/dist`` 已构建时 ``/`` 返回 ``text/html``。
- 构建产物里的 ``/assets/*.js`` 以 JavaScript MIME 返回（Windows 注册表把 ``.js``
  记为 ``text/plain`` 时 ES module 会被浏览器拒载）。

隔离手段：`TestClient` 直接构造、不用上下文管理器，因此不会触发 lifespan，
既不启动 Playwright 浏览器也不启动 APScheduler，更不监听真实端口；
依赖 ``dist`` 的两个用例在未构建时 ``skipTest``，本地不安装前端也能跑通。
"""

import re
import unittest

from fastapi.testclient import TestClient

from main import FRONTEND_DIST_DIR, app


class HealthEndpointTests(unittest.TestCase):
    """健康检查与静态托管的端点级测试（无浏览器、无网络）。"""

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
