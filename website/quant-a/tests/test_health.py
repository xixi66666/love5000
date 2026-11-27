"""健康检查、工作台静态页面与版本状态接口的冒烟测试。

覆盖分支：`GET /api/health` 的成功响应结构（顶层 `success` 与稳定的 `service`
标识）、`GET /` 返回的工作台页面关键片段、`/static` 下 CSS/JS 的可访问性，
以及 `GET /api/status` 暴露的模型版本、Provider 名称和 DuckDB 存储路径。

隔离方式：全部通过 FastAPI `TestClient` 在进程内调用，按 `configs/app.yaml`
构造真实 pipeline，不启动 uvicorn、不发任何上游行情请求。
"""

from fastapi.testclient import TestClient

from main import app


def test_health_returns_success_payload():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "service": "quant-a",
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
