from datetime import date

from fastapi.testclient import TestClient

from main import app
from quant.api.routes import daily_sync_lock, get_pipeline, run_daily_sync_task
from quant.providers.mock_provider import MockProvider
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository


def build_client(tmp_path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    return TestClient(app), repository


def clear_overrides():
    app.dependency_overrides.clear()
    try:
        daily_sync_lock.release()
    except RuntimeError:
        pass


def test_data_sync_and_scoring_pipeline(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        sync_response = client.post("/api/data/sync", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["CSI300"],
        })
        assert sync_response.status_code == 200
        sync_payload = sync_response.json()
        assert sync_payload["success"] is True
        assert sync_payload["data"]["data_version"] == "mock-2024-q1"
        assert sync_payload["data"]["calendar_count"] > 0
        assert sync_payload["data"]["stock_count"] > 0
        assert sync_payload["data"]["daily_bar_count"] > 0
        assert sync_payload["data"]["index_member_count"] > 0

        score_response = client.post("/api/scores/run", json={
            "trade_date": "2024-03-29",
            "index_codes": ["CSI300"],
        })
        assert score_response.status_code == 200
        payload = score_response.json()
        assert payload["success"] is True
        assert payload["data"]["trade_date"] == "2024-03-29"
        assert len(payload["data"]["scores"]) == 6

        first_score = payload["data"]["scores"][0]
        assert first_score["rank"] == 1
        assert first_score["model_version"] == "v0.1"
        assert first_score["data_version"] == "mock-2024-q1"
        assert {"code", "name", "industry", "total_score"}.issubset(first_score.keys())
    finally:
        clear_overrides()


def test_status_reports_local_data_integrity_and_latest_score_date(tmp_path):
    client, repository = build_client(tmp_path)
    try:
        client.post("/api/data/sync", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["FULL_MARKET"],
        })

        response = client.get("/api/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        integrity = payload["data"]["data_integrity"]
        assert integrity["stock_count"] == 6
        assert integrity["daily_bar_count"] > 0
        assert integrity["valuation_count"] > 0
        assert integrity["financial_count"] == 6
        assert integrity["latest_score_date"] == "2024-03-29"
        assert integrity["score_ready"] is True
        assert integrity["score_ready_stock_count"] == 6
        assert integrity["market_remaining_count"] == 0
        assert repository.count_rows("index_member") == 6
    finally:
        clear_overrides()


def test_status_reports_missing_valuation_as_not_score_ready(tmp_path):
    client, repository = build_client(tmp_path)
    try:
        client.post("/api/data/sync", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["FULL_MARKET"],
        })
        repository.connection.execute("delete from valuation")

        response = client.get("/api/status")

        assert response.status_code == 200
        payload = response.json()
        integrity = payload["data"]["data_integrity"]
        assert integrity["valuation_count"] == 0
        assert integrity["latest_score_date"] is None
        assert integrity["score_ready"] is False
        assert "估值数据为空" in integrity["blocking_reasons"]
    finally:
        clear_overrides()


def test_run_scores_returns_clear_error_when_local_data_is_incomplete(tmp_path):
    client, repository = build_client(tmp_path)
    try:
        client.post("/api/data/sync", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["FULL_MARKET"],
        })
        repository.connection.execute("delete from valuation")

        response = client.post("/api/scores/run", json={
            "trade_date": "2024-03-29",
            "index_codes": ["FULL_MARKET"],
        })

        assert response.status_code == 400
        payload = response.json()
        assert payload["success"] is False
        assert "本地数据不足，无法评分" in payload["message"]
        assert "估值数据为空" in payload["message"]
    finally:
        clear_overrides()


def test_daily_sync_endpoint_reuses_cached_snapshot(tmp_path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())
    pipeline.sync_data_daily("2024-01-02", "2024-03-31", ["CSI300"])
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    client = TestClient(app)
    try:
        response = client.post("/api/data/sync-daily", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["CSI300"],
        })

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["status"] == "cached"
        assert payload["data"]["cache_hit"] is True
        assert payload["data"]["stock_count"] == 6
    finally:
        clear_overrides()


def test_daily_sync_endpoint_starts_background_task_when_snapshot_missing(tmp_path):
    client, _ = build_client(tmp_path)
    calls = []

    def record_task(pipeline, request):
        try:
            calls.append((pipeline, request.start_date, request.end_date, request.index_codes))
        finally:
            daily_sync_lock.release()

    app.dependency_overrides[run_daily_sync_task] = lambda: record_task
    try:
        response = client.post("/api/data/sync-daily", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["CSI300"],
        })

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["status"] == "syncing"
        assert payload["data"]["cache_hit"] is False
        assert payload["data"]["message"] == "今日数据同步已启动，请稍后查看。"
        assert len(calls) == 1
        assert calls[0][1:] == ("2024-01-02", "2024-03-31", ["CSI300"])
    finally:
        clear_overrides()


def test_daily_sync_endpoint_continues_background_task_when_cached_snapshot_is_incomplete(tmp_path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())
    pipeline.sync_data_daily_fast(
        "2024-01-02",
        "2024-03-31",
        ["FULL_MARKET"],
        sync_date=date.today().isoformat(),
    )
    calls = []

    def record_task(pipeline_arg, request):
        try:
            calls.append((pipeline_arg, request.start_date, request.end_date, request.index_codes))
        finally:
            daily_sync_lock.release()

    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[run_daily_sync_task] = lambda: record_task
    client = TestClient(app)
    try:
        response = client.post("/api/data/sync-daily", json={
            "start_date": "2024-01-02",
            "end_date": "2024-03-31",
            "index_codes": ["FULL_MARKET"],
        })

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["status"] == "syncing"
        assert payload["data"]["cache_hit"] is True
        assert payload["data"]["market_remaining_count"] == 6
        assert payload["data"]["valuation_remaining_count"] == 6
        assert len(calls) == 1
    finally:
        clear_overrides()


def test_backtest_report_pipeline(tmp_path):
    client, _ = build_client(tmp_path)
    try:
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
        assert payload["data"]["skipped_score_dates"] == []

        backtest = payload["data"]["backtest"]
        assert backtest["experiment_id"].startswith("bt-")
        assert len(backtest["nav"]) > 0
        assert len(backtest["orders"]) > 0
        assert len({order["code"] for order in backtest["orders"] if order["side"] == "buy"}) == 6

        report = payload["data"]["report"]
        assert report["experiment_id"] == backtest["experiment_id"]
        assert report["metrics"]["order_count"] > 0
        assert report["nav"] == backtest["nav"]
        assert report["orders"] == backtest["orders"]
        assert report["known_biases"]
    finally:
        clear_overrides()
