"""公开刷新端点 `POST /api/v1/collections/refresh` 的判定链。

该端点的顺序是：先看最近一次任务是否还在冷却期（非 `FAILED` 且不足 30 分钟 → 429
`REFRESH_COOLDOWN`），再抢 MySQL 命名锁（抢不到 → 409 `COLLECTION_ALREADY_RUNNING`），
两者都通过才排后台任务并回 202。`FAILED` 被特意排除在冷却之外，否则一次网络抖动
就会把用户锁在半小时之外。

隔离方式：`CollectionRunStore`、`acquire_collection_lock`、`run_collection` 全部按
模块路径 patch；`TestClient` 复用真实 `app.main:app` 的路由表，但请求路径上没有任何
真实数据库会话被打开，也不会有采集跑出来。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _recent_run(started_minutes_ago: int) -> MagicMock:
    """造一条“N 分钟前开始”的假采集任务。

    刻意去掉 `tzinfo`：MySQL 取回的 `started_at` 是无时区 DATETIME，
    端点需要自己补成 UTC 再算冷却，这里保持同样的形状才能覆盖那段补时区逻辑。
    """
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


def test_failed_collection_can_be_retried_without_success_cooldown() -> None:
    run = _recent_run(1)
    run.status = "FAILED"
    with (
        patch("app.api.v1.collections.CollectionRunStore") as store_cls,
        patch("app.api.v1.collections.acquire_collection_lock") as lock,
        patch("app.api.v1.collections.run_collection"),
    ):
        store_cls.return_value.latest = AsyncMock(return_value=run)
        lock.return_value = MagicMock()
        response = client.post("/api/v1/collections/refresh")
    assert response.status_code == 202
