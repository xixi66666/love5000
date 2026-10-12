from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.last30days.service import (
    Last30DaysNotConfigured,
    diagnose_last30days,
    fetch_last30days,
)

AGENT_EXPORT = {
    "schema_version": "1.0",
    "query": "OpenAI",
    "generated_at": "2026-08-21T00:00:00Z",
    "window_days": 30,
    "source_status": {
        "github": "ok",
        "hackernews": "ok",
        "polymarket": "no-results",
        "reddit": "ok",
    },
    "clusters": [
        {
            "title": "Developer reactions",
            "summary": "Developers discussed the latest changes.",
            "sources": ["reddit", "hackernews"],
            "engagement_total": 320,
        }
    ],
    "results": [
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
}


@pytest.mark.asyncio
async def test_fetch_uses_multisource_agent_export() -> None:
    runner = AsyncMock(return_value=AGENT_EXPORT)
    with patch("app.last30days.service._run_last30days", runner):
        result = await fetch_last30days(query="OpenAI", limit=10)

    assert result["status"] == "working"
    assert result["query"] == "OpenAI"
    assert result["sources"] == ["github", "hackernews", "polymarket", "reddit"]
    assert result["source_status"]["reddit"] == "ok"
    assert result["clusters"][0]["title"] == "Developer reactions"
    assert result["items"][0]["source"] == "reddit"
    assert result["items"][0]["engagement"]["comments"] == 42
    args = runner.await_args.args[0]
    assert args[0] == "OpenAI"
    assert "--emit=json" in args
    assert "--json-profile=agent" in args
    assert "--auto-resolve" in args


@pytest.mark.asyncio
async def test_fetch_reports_unconfigured_runtime() -> None:
    runner = AsyncMock(side_effect=Last30DaysNotConfigured("runtime missing"))
    with patch("app.last30days.service._run_last30days", runner):
        result = await fetch_last30days(query="OpenAI", limit=10)

    assert result["status"] == "unconfigured"
    assert result["items"] == []
    assert result["message"] == "runtime missing"


@pytest.mark.asyncio
async def test_diagnose_returns_available_sources() -> None:
    runner = AsyncMock(
        return_value={
            "safe": True,
            "available_sources": ["reddit", "hackernews", "polymarket", "github", "grounding"],
        }
    )
    with patch("app.last30days.service._run_last30days", runner):
        result = await diagnose_last30days()

    assert result["status"] == "working"
    assert result["sources"] == ["reddit", "hackernews", "polymarket", "github", "grounding"]
    runner.assert_awaited_once_with(["--diagnose"])

