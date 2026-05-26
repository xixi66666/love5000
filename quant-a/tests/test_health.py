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
