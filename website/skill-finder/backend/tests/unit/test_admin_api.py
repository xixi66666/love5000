"""管理端点的鉴权与并发保护。

覆盖 `/api/v1/admin/collections` 与 `/api/v1/admin/introductions`：缺少或错误的
`X-Admin-Key` 一律 401，正确的密钥才排队后台任务并回 202；采集命名锁抢不到时回 409
且带稳定错误码 `COLLECTION_ALREADY_RUNNING`；非法 category 由 FastAPI 校验回 422。

隔离方式：只把 `admin.router` 挂到一个空白 `FastAPI()` 上，绕开 `app.main` 的数据库
依赖；`dependencies.settings.admin_key` 由 fixture 换成测试值并在用例结束后还原；
锁与后台任务（`acquire_collection_lock` / `run_collection` / `run_introduction_backfill`）
全部 monkeypatch 成本地替身，不触达 MySQL 命名锁，也不发起真实采集。
"""

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
    """只挂 admin 路由的测试客户端，后台密钥换成固定测试值。

    不挂载其余路由可以避免模块导入时就要求数据库会话；`admin_key` 写入全局
    `dependencies.settings`，monkeypatch 会在用例结束后自动复原，不会污染其他测试。
    """
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
    # 用替身接管命名锁与后台采集：真实实现会连 MySQL 命名锁并抓取 GitHub。
    class FakeLease:
        """可释放的假租约，只为了让 202 分支拿到非 None 的锁对象。"""

        async def release(self) -> None:
            pass

    async def fake_acquire():
        """模拟抢锁成功。"""
        return FakeLease()

    async def fake_run(lease) -> None:
        """吞掉后台采集协程，避免用例真的发起网络请求。"""
        pass  # noqa: PIE790

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
        """返回 None 表示命名锁已被另一轮采集持有。"""
        return None  # noqa: RET501

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
    # 记录补全任务收到的关键字参数，用来确认查询串（category/limit/order）原样透传。
    calls: list[dict] = []

    async def fake_backfill(**kwargs) -> None:
        """只记账、不真正调用模型。"""
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

