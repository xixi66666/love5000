from fastapi.testclient import TestClient

from main import app


def test_health_returns_success_payload():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "service": "quant-a",
            "status": "ok",
            "port": 5175,
        },
        "message": "",
    }


def test_workbench_page_is_served():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "quant-a" in response.text
    assert "多因子量化研究工作台" in response.text
    assert "运行回测" in response.text
    assert "操作流水" in response.text
    assert 'id="orderTableBody"' in response.text
    assert 'href="/static/styles.css"' in response.text
    assert 'src="/static/app.js"' in response.text

    css_response = client.get("/static/styles.css")
    js_response = client.get("/static/app.js")

    assert css_response.status_code == 200
    assert js_response.status_code == 200


def test_status_exposes_configured_versions():
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["service"] == "quant-a"
    assert payload["data"]["model_version"] == "v0.1"
    assert payload["data"]["provider"] == "akshare"
    assert payload["data"]["storage"]["duckdb_path"].endswith("data/quant.duckdb")
