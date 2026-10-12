import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import dependencies
from app.api.dependencies import verify_admin_key
from app.api.v1 import admin

SECRET = "super-secret-admin-key-value"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(dependencies.settings, "admin_key", SecretStr(SECRET))
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/v1")
    return TestClient(app)


def test_missing_admin_key_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/admin/collections")
    assert response.status_code == 401


def test_wrong_admin_key_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/collections",
        headers={"X-Admin-Key": "not-the-secret"},
    )
    assert response.status_code == 401


def test_correct_admin_key_returns_202(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeLease:
        async def release(self) -> None:
            pass

    async def fake_acquire():
        return FakeLease()

    async def fake_run(lease) -> None:
        pass

    monkeypatch.setattr(admin, "acquire_collection_lock", fake_acquire)
    monkeypatch.setattr(admin, "run_collection", fake_run)
    response = client.post(
        "/api/v1/admin/collections",
        headers={"X-Admin-Key": SECRET},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def test_lock_conflict_returns_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_acquire():
        return None

    monkeypatch.setattr(admin, "acquire_collection_lock", fake_acquire)
    response = client.post(
        "/api/v1/admin/collections",
        headers={"X-Admin-Key": SECRET},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COLLECTION_ALREADY_RUNNING"


def test_verify_admin_key_does_not_leak_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies.settings, "admin_key", SecretStr(SECRET))
    assert verify_admin_key(SECRET) is True
    assert verify_admin_key("super-secret-admin-key-value-2") is False
    assert verify_admin_key(None) is False


def test_trigger_introductions_returns_202(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    async def fake_backfill(**kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(admin, "run_introduction_backfill", fake_backfill)
    response = client.post(
        "/api/v1/admin/introductions?category=SKILL&limit=5",
        headers={"X-Admin-Key": SECRET},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert calls == [{"category": "SKILL", "limit": 5, "order": None}]


def test_trigger_introductions_rejects_invalid_category(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/admin/introductions?category=BAD",
        headers={"X-Admin-Key": SECRET},
    )
    assert response.status_code == 422


def test_trigger_introductions_requires_admin_key(client: TestClient) -> None:
    response = client.post("/api/v1/admin/introductions?limit=5")
    assert response.status_code == 401

