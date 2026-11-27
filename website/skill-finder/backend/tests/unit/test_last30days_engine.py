"""last30days 服务层对 skill 导出的解析与降级。

覆盖 `app.last30days.service` 的两个入口：

- `fetch_last30days` 要把 agent JSON 导出映射成接口契约（`status`、去重后的
  `sources`、`source_status`、`clusters`、`items`），命令行固定带
  `--emit=json --json-profile=agent --auto-resolve`；
- 本机没装 skill 时底层抛 `Last30DaysNotConfigured`，这里必须降级成
  `status=unconfigured` 的空结果，不能变成 500；
- `diagnose_last30days` 只读取 `available_sources` 并标记为 `working`。

隔离方式：真正启动 Node 子进程的 `_run_last30days` 被 patch 成 `AsyncMock`，
所以既不安装也不执行外部 skill，不发起任何网络请求。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.last30days.service import (
    Last30DaysNotConfigured,
    diagnose_last30days,
    fetch_last30days,
)

# 与 last30days skill `--json-profile=agent` 输出一致的样例：四路来源状态
# （polymarket 明确为 no-results）、一个簇、一条带互动数据的结果。
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

