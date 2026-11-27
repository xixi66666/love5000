"""仓库列表 / 详情与统计接口的响应契约。

覆盖 `app.api.v1.repositories` 与 `app.api.v1.stats`：

- 列表返回固定字段集合，且 `page` / `page_size` / `sort` / `category` 非法取值一律
  422（这些参数直接决定 SQL 排序与过滤，不能放过）；
- 详情 404 走统一错误体，带稳定 `code` 与 `request_id`，便于前端提示和查日志；
- 统计响应除原有三项外必须带后端补的 `last_run_id` / `last_run_error` /
  `last_run_warning`，前端刷新轮询依赖这三个可空字段。

另外覆盖 `_parse_introduction` 的三种历史存储格式：完整结构（顺带过滤空白亮点）、
旧版只存部分字段、以及更早的纯文本。

隔离方式：用独立 `FastAPI()` 只挂需要的路由，并通过 `app.dependency_overrides`
把 `get_repository_service` / `get_stats_service` 换成文件内的假实现，
因此不连 MySQL；注册真实 `api_error_handler` 让错误体与线上一致。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import REPOSITORY_NOT_FOUND, ApiError, api_error_handler
from app.api.v1 import repositories, stats
from app.schemas.common import PageParams
from app.schemas.repository import RepositoryDetail, RepositoryListItem
from app.services.repository_service import _parse_introduction

# 列表接口的样例条目：字段齐全，便于断言序列化后的形状与默认值。
DUMMY_ITEM = RepositoryListItem(
    id=1,
    owner="octocat",
    name="agent-hub",
    description="An agent framework",
    html_url="https://github.com/octocat/agent-hub",
    language="Python",
    topics=["ai-agent"],
    categories=["AGENT"],
    stars_count=1500,
    daily_stars=20,
    weekly_stars=100,
    monthly_stars=400,
    last_synced_at="2026-08-10T00:00:00Z",
    trend=[],
)


class FakeRepositoryService:
    """假仓储服务：列表固定返回一条 `DUMMY_ITEM` 并记下过滤参数。

    详情只认 `octocat/agent-hub`，其余情况抛 `ApiError(REPOSITORY_NOT_FOUND)`
    模拟“仓库不存在”，让 404 分支走真实错误处理器。
    """

    def __init__(self) -> None:
        self.last_params: dict[str, Any] = {}
        self.detail: RepositoryDetail | None = None

    async def list_repositories(self, session, page_params: PageParams, **filters):
        self.last_params = {**filters, "page": page_params.page, "page_size": page_params.page_size}
        return {
            "items": [DUMMY_ITEM],
            "page": 1,
            "page_size": 20,
            "total": 1,
            "last_successful_collection_at": "2026-08-10T00:00:00Z",
        }

    async def get_detail(self, session, owner: str, name: str) -> RepositoryDetail | None:
        if self.detail is None and (owner, name) == ("octocat", "agent-hub"):
            return RepositoryDetail(
                id=1,
                owner="octocat",
                name="agent-hub",
                description="An agent framework",
                html_url="https://github.com/octocat/agent-hub",
                language="Python",
                topics=["ai-agent"],
                categories=["AGENT"],
                matched_rules=["topic:ai-agent"],
                stars_count=1500,
                forks_count=50,
                open_issues_count=3,
                daily_stars=20,
                weekly_stars=100,
                monthly_stars=400,
                last_synced_at="2026-08-10T00:00:00Z",
                github_created_at="2026-01-01T00:00:00Z",
                trend=[],
            )
        raise ApiError(REPOSITORY_NOT_FOUND, "Repository not found", 404)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """只挂 repositories 路由的测试客户端，服务依赖被替换成假实现。"""
    service = FakeRepositoryService()

    async def service_dep():
        return service

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.dependency_overrides[repositories.get_repository_service] = service_dep
    app.include_router(repositories.router, prefix="/api/v1")
    return TestClient(app)


def test_list_contract_shape(client: TestClient) -> None:
    response = client.get("/api/v1/repositories")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "items",
        "page",
        "page_size",
        "total",
        "last_successful_collection_at",
    }
    item = body["items"][0]
    assert item["owner"] == "octocat"
    assert item["daily_stars"] == 20
    assert item["trend"] == []


# 六种非法参数：页码为 0、页码非数字、页大小越界（101 / 0）、未知 sort、未知 category。
# 每种都要 422，且错误信息里点出出错字段名，前端才能定位到对应输入框。
@pytest.mark.parametrize(
    ("params", "invalid"),
    [
        ({"page": 0}, "page"),
        ({"page": "abc"}, "page"),
        ({"page_size": 101}, "page_size"),
        ({"page_size": 0}, "page_size"),
        ({"sort": "bad_sort"}, "sort"),
        ({"category": "BAD"}, "category"),
    ],
)
def test_list_rejects_invalid_params(
    client: TestClient, params: dict[str, Any], invalid: str
) -> None:
    response = client.get("/api/v1/repositories", params=params)
    assert response.status_code == 422
    assert invalid in response.text


def test_list_accepts_monthly_sort_and_plugin_category(client: TestClient) -> None:
    response = client.get(
        "/api/v1/repositories",
        params={"sort": "monthly_stars", "category": "PLUGIN"},
    )
    assert response.status_code == 200


def test_parse_introduction_rich_fields() -> None:
    raw = json.dumps(
        {
            "introduction": "项目简介",
            "highlights": ["亮点一", " "],
            "requirements": ["Node.js 22+"],
            "usage": "运行 npm install",
            "audience": "开发者",
            "domains": ["AI Agent"],
        },
        ensure_ascii=False,
    )
    parsed = _parse_introduction(raw)
    assert parsed is not None
    assert parsed.introduction == "项目简介"
    assert parsed.highlights == ["亮点一"]
    assert parsed.requirements == ["Node.js 22+"]
    assert parsed.usage == "运行 npm install"
    assert parsed.audience == "开发者"
    assert parsed.domains == ["AI Agent"]


def test_parse_introduction_legacy_format() -> None:
    raw = json.dumps(
        {"introduction": "旧格式", "usage": "用法", "domains": ["RAG"]},
        ensure_ascii=False,
    )
    parsed = _parse_introduction(raw)
    assert parsed is not None
    assert parsed.introduction == "旧格式"
    assert parsed.highlights == []
    assert parsed.requirements == []
    assert parsed.audience == ""


def test_parse_introduction_plain_text_fallback() -> None:
    parsed = _parse_introduction("一段纯文本介绍")
    assert parsed is not None
    assert parsed.introduction == "一段纯文本介绍"


def test_detail_success(client: TestClient) -> None:
    response = client.get("/api/v1/repositories/octocat/agent-hub")
    assert response.status_code == 200
    body = response.json()
    assert body["owner"] == "octocat"
    assert body["name"] == "agent-hub"
    assert body["matched_rules"] == ["topic:ai-agent"]


def test_detail_404(client: TestClient) -> None:
    response = client.get("/api/v1/repositories/octocat/ghost")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "REPOSITORY_NOT_FOUND"
    assert "request_id" in body


def test_stats_contract() -> None:
    class FakeStatsService:
        async def get_stats(self, session):
            return {
                "total_repositories": 10,
                "positive_growth_today": 4,
                "last_successful_collection_at": "2026-08-10T00:00:00Z",
                "last_run_status": "SUCCESS",
            }

        async def get_languages(self, session):
            return [{"language": "Python", "count": 6}]

    app = FastAPI()

    async def stats_dep():
        return FakeStatsService()

    app.dependency_overrides[stats.get_stats_service] = stats_dep
    app.include_router(stats.router, prefix="/api/v1")
    client = TestClient(app)

    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    assert set(response.json()) == {
        "total_repositories",
        "positive_growth_today",
        "last_successful_collection_at",
        "last_run_status",
        "last_run_id",
        "last_run_error",
        "last_run_warning",
    }

    langs = client.get("/api/v1/languages")
    assert langs.status_code == 200
    assert langs.json() == [{"language": "Python", "count": 6}]
