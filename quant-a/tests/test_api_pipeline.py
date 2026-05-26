from fastapi.testclient import TestClient

from main import app


def test_data_sync_and_scoring_pipeline():
    client = TestClient(app)

    sync_response = client.post("/api/data/sync", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
    })
    assert sync_response.status_code == 200
    assert sync_response.json()["success"] is True

    score_response = client.post("/api/scores/run", json={
        "trade_date": "2024-03-29",
        "index_codes": ["CSI300"],
    })
    assert score_response.status_code == 200
    payload = score_response.json()
    assert payload["success"] is True
    assert len(payload["data"]["scores"]) == 6


def test_backtest_report_pipeline():
    client = TestClient(app)
    client.post("/api/data/sync", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
    })

    response = client.post("/api/backtests/run", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
        "initial_cash": 1000000,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["report"]["metrics"]["order_count"] > 0
    assert payload["data"]["report"]["known_biases"]
