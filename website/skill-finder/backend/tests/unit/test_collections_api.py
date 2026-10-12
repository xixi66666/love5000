from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _recent_run(started_minutes_ago: int) -> MagicMock:
    run = MagicMock()
    run.started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        minutes=started_minutes_ago
    )
    return run


def test_refresh_accepted_when_no_previous_run() -> None:
    with (
        patch("app.api.v1.collections.CollectionRunStore") as store_cls,
        patch("app.api.v1.collections.acquire_collection_lock") as lock,
        patch("app.api.v1.collections.run_collection"),
    ):
        store_cls.return_value.latest = AsyncMock(return_value=None)
        lock.return_value = MagicMock()
        response = client.post("/api/v1/collections/refresh")

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    lock.assert_awaited_once()


def test_refresh_rejected_within_cooldown() -> None:
    with patch("app.api.v1.collections.CollectionRunStore") as store_cls:
        store_cls.return_value.latest = AsyncMock(return_value=_recent_run(5))
        response = client.post("/api/v1/collections/refresh")

    assert response.status_code == 429
    payload = response.json()
    assert payload["code"] == "REFRESH_COOLDOWN"
    assert "分钟后再试" in payload["message"]


def test_refresh_allowed_after_cooldown() -> None:
    with (
        patch("app.api.v1.collections.CollectionRunStore") as store_cls,
        patch("app.api.v1.collections.acquire_collection_lock") as lock,
        patch("app.api.v1.collections.run_collection"),
    ):
        store_cls.return_value.latest = AsyncMock(return_value=_recent_run(120))
        lock.return_value = MagicMock()
        response = client.post("/api/v1/collections/refresh")

    assert response.status_code == 202


def test_refresh_conflict_when_collection_already_running() -> None:
    with (
        patch("app.api.v1.collections.CollectionRunStore") as store_cls,
        patch(
            "app.api.v1.collections.acquire_collection_lock",
            AsyncMock(return_value=None),
        ),
    ):
        store_cls.return_value.latest = AsyncMock(return_value=_recent_run(120))
        response = client.post("/api/v1/collections/refresh")

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == "COLLECTION_ALREADY_RUNNING"
