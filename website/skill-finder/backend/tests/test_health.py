"""单元测试：健康检查、API 404 边界与前端静态托管。

覆盖：``/api/v1/health`` 的旧探针、``/api/health`` 的统一健康结构
（``success`` + ``service``）、未匹配的 ``/api/**`` 不会被 SPA fallback 吞掉、
``dist`` 已构建时 ``/`` 返回 HTML、构建出的 JS 资源带 JavaScript MIME
（Windows 的 ``text/plain`` 回归）。

隔离：全部通过 ``TestClient`` 直接调用应用，不启动真实端口、不连接 MySQL；
涉及 ``dist`` 的用例在未构建时直接返回，不会因为缺少构建产物而失败。
"""
import re

from fastapi.testclient import TestClient

from app.main import FRONTEND_DIST_DIR, app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_service_health_returns_unified_status() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["service"] == "skill-finder"


def test_unknown_api_path_is_not_swallowed_by_spa_fallback() -> None:
    response = TestClient(app).get("/api/does-not-exist")
    assert response.status_code == 404


def test_frontend_index_is_served_when_dist_is_built() -> None:
    if not (FRONTEND_DIST_DIR / "index.html").is_file():
        return

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_built_javascript_asset_is_served_with_javascript_mime_type() -> None:
    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.is_file():
        return

    html = index_file.read_text(encoding="utf-8")
    match = re.search(r'src="(?:/[^"/]*)*(/assets/[^"/]+\.js)"', html)
    assert match is not None, "built index.html should reference a JS asset"

    response = TestClient(app).get(match.group(1))
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", ""), (
        "ES module scripts require a JavaScript MIME type (text/plain breaks them)"
    )
