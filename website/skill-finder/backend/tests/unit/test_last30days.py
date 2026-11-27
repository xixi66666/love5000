"""last30days 多源研究接口的对外契约。

覆盖 `/api/v1/last30days`、`/api/v1/last30days/status` 以及
`/api/v1/last30days/rankings` 与其 `/refresh`：请求里的 `query` 要先去掉首尾空白再
交给服务层；空主题和未知 `direction` 由 FastAPI 校验回 422；服务层返回
`unconfigured`（本机没装 last30days skill）时必须原样透出 `message`，不能包装成
“成功但为空”；`direction` 缺省为 `agent`。

隔离方式：只把 `app.api.v1.last30days` 中的 `fetch_last30days` /
`diagnose_last30days` / `get_ranking` / `refresh_ranking` patch 成 `AsyncMock`，
不启动 Node skill、不访问 Reddit / Hacker News / GitHub 等外部来源，也不连数据库。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _research_result() -> dict:
    """构造一份多源研究结果，字段与 last30days skill 的 agent 导出对齐。"""
    return {
        "status": "working",
        "query": "OpenAI",
        "items": [
            {
                "candidate_id": "reddit-1",
                "title": "What developers are saying",
                "source": "reddit",
                "url": "https://www.reddit.com/r/example/1",
                "published_at": "2026-08-20T00:00:00Z",
                "summary": "A grounded community summary.",
                "engagement": {"score": 210, "comments": 42},
                "relevance_score": 0.95,
                "cluster": 0,
            }
        ],
        "clusters": [
            {
                "title": "Developer reactions",
                "summary": "Developers discussed the latest changes.",
                "sources": ["reddit", "hackernews"],
                "engagement_total": 320,
            }
        ],
        "sources": ["github", "hackernews", "reddit"],
        "source_status": {
            "github": "ok",
            "hackernews": "ok",
            "reddit": "ok",
        },
        "fetched_at": "2026-08-21T00:00:00Z",
        "message": None,
    }


def test_research_endpoint_returns_multisource_result() -> None:
    runner = AsyncMock(return_value=_research_result())
    with patch("app.api.v1.last30days.fetch_last30days", runner):
        response = client.post("/api/v1/last30days", json={"query": "  OpenAI  ", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "OpenAI"
    assert payload["sources"] == ["github", "hackernews", "reddit"]
    assert payload["clusters"][0]["title"] == "Developer reactions"
    assert payload["items"][0]["source"] == "reddit"
    runner.assert_awaited_once_with(query="OpenAI", limit=10)


def test_research_endpoint_rejects_blank_topic() -> None:
    response = client.post("/api/v1/last30days", json={"query": "   "})

    assert response.status_code == 422


def test_status_endpoint_reports_available_sources() -> None:
    runner = AsyncMock(
        return_value={
            "status": "working",
            "sources": ["reddit", "hackernews", "polymarket", "github", "grounding"],
            "message": None,
        }
    )
    with patch("app.api.v1.last30days.diagnose_last30days", runner):
        response = client.get("/api/v1/last30days/status")

    assert response.status_code == 200
    assert response.json()["sources"] == [
        "reddit",
        "hackernews",
        "polymarket",
        "github",
        "grounding",
    ]


def test_research_endpoint_preserves_unconfigured_status() -> None:
    result = _research_result()
    result.update(
        {
            "status": "unconfigured",
            "items": [],
            "clusters": [],
            "sources": [],
            "source_status": {},
            "message": "runtime missing",
        }
    )
    with patch("app.api.v1.last30days.fetch_last30days", AsyncMock(return_value=result)):
        response = client.post("/api/v1/last30days", json={"query": "OpenAI"})

    assert response.status_code == 200
    assert response.json()["status"] == "unconfigured"
    assert response.json()["message"] == "runtime missing"


def _ranking_result(direction: str = "agent") -> dict:
    """构造一份榜单报告；`direction` 用于确认接口把这个参数原样传给服务层。"""
    return {
        "direction": direction,
        "status": "working",
        "items": [
            {
                "candidate_id": "reddit-1",
                "title": "What developers are saying",
                "source": "reddit",
                "url": "https://www.reddit.com/r/example/1",
                "published_at": "2026-08-20T00:00:00Z",
                "summary": "A grounded community summary.",
                "engagement": {"score": 210, "comments": 42},
                "relevance_score": 0.95,
                "cluster": 0,
            }
        ],
        "clusters": [],
        "sources": ["reddit"],
        "source_status": {"reddit": "ok"},
        "fetched_at": "2026-08-21T00:00:00Z",
        "message": None,
    }


def test_rankings_endpoint_returns_cached_report() -> None:
    runner = AsyncMock(return_value=_ranking_result())
    with patch("app.api.v1.last30days.get_ranking", runner):
        response = client.get("/api/v1/last30days/rankings", params={"direction": "agent"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] == "agent"
    assert payload["items"][0]["candidate_id"] == "reddit-1"
    assert runner.await_count == 1
    assert runner.await_args.args[1] == "agent"


def test_rankings_endpoint_defaults_to_agent() -> None:
    runner = AsyncMock(return_value=_ranking_result())
    with patch("app.api.v1.last30days.get_ranking", runner):
        response = client.get("/api/v1/last30days/rankings")

    assert response.status_code == 200
    assert runner.await_args.args[1] == "agent"


def test_rankings_endpoint_rejects_unknown_direction() -> None:
    response = client.get("/api/v1/last30days/rankings", params={"direction": "mcp"})

    assert response.status_code == 422


def test_refresh_endpoint_passes_direction() -> None:
    runner = AsyncMock(return_value=_ranking_result(direction="skill"))
    with patch("app.api.v1.last30days.refresh_ranking", runner):
        response = client.post(
            "/api/v1/last30days/rankings/refresh", json={"direction": "skill"}
        )

    assert response.status_code == 200
    assert response.json()["direction"] == "skill"
    runner.assert_awaited_once()
    assert runner.await_args.args[1] == "skill"


def test_refresh_endpoint_rejects_unknown_direction() -> None:
    response = client.post("/api/v1/last30days/rankings/refresh", json={"direction": "mcp"})

    assert response.status_code == 422
