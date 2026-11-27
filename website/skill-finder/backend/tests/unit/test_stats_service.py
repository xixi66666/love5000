"""首页统计服务对采集状态的降级文案。

`StatsService.get_stats` 除了聚合数字，还要把 `collection_runs.error_summary`
翻译成固定中文提示：`FAILED` 走 `last_run_error`，`PARTIAL` 走 `last_run_warning`，
两条通道按状态互斥。这些文案会直接进 `/api/v1/stats` 响应，因此边界是
「原始异常、SQL、连接串、令牌一律不得回显」，只能给固定提示。

隔离方式：`AsyncMock` 会话按调用顺序脚本化 `scalar` / `execute` 的返回值，
结果行用 `MagicMock` 顶替，不连数据库、不写事务。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.stats_service import StatsService


# 参数表是「error_summary 关键字 → 固定提示」的映射：前三行各命一个专用分支，
# 最后一行的异常原文里塞了 password/token，用来确认认不出时降级为通用文案且不回显。
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
