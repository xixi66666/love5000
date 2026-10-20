from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.stats_service import StatsService


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("TrendingScrapeError: daily Timeout", "连接 GitHub 超时"),
        ("GitHubAuthError: authentication failed", "GitHub 认证失败"),
        ("GitHubRateLimitError: rate limit exceeded", "GitHub 请求额度已用尽"),
        ("private password and token", "采集执行失败"),
    ],
)
async def test_stats_exposes_run_identity_and_safe_failure_message(summary, expected):
    latest = SimpleNamespace(id=4, status="FAILED", error_summary=summary)
    success_result, latest_result = MagicMock(), MagicMock()
    success_result.scalar_one_or_none.return_value = None
    latest_result.scalar_one_or_none.return_value = latest
    session = AsyncMock()
    session.scalar.side_effect = [20, 8]
    session.execute.side_effect = [success_result, latest_result]
    result = await StatsService().get_stats(session)
    assert result["last_run_id"] == 4
    assert expected in result["last_run_error"]
    assert "private password" not in result["last_run_error"]


async def test_partial_introductions_are_a_warning_instead_of_success_or_total_failure():
    latest = SimpleNamespace(id=5, status="PARTIAL", error_summary="INTRO_AUTH_FAILED: missing=7")
    success_result, latest_result = MagicMock(), MagicMock()
    success_result.scalar_one_or_none.return_value = None
    latest_result.scalar_one_or_none.return_value = latest
    session = AsyncMock()
    session.scalar.side_effect = [34, 8]
    session.execute.side_effect = [success_result, latest_result]
    result = await StatsService().get_stats(session)
    assert result["last_run_error"] is None
    assert "简介服务认证失败" in result["last_run_warning"]
