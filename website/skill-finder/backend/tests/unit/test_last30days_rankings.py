from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.last30days.service import (
    DIRECTION_QUERIES,
    get_ranking,
    rank_items,
    refresh_ranking,
)


def _item(candidate_id: str, engagement: dict) -> dict:
    return {
        "candidate_id": candidate_id,
        "title": f"title-{candidate_id}",
        "source": "reddit",
        "url": f"https://example.com/{candidate_id}",
        "published_at": "2026-08-20T00:00:00Z",
        "summary": "summary",
        "engagement": engagement,
        "relevance_score": 0.9,
        "cluster": 0,
    }


def _engine_result(items: list[dict]) -> dict:
    return {
        "status": "working",
        "query": "AI agents",
        "items": items,
        "clusters": [],
        "sources": ["reddit"],
        "source_status": {"reddit": "ok"},
        "fetched_at": "2026-08-21T00:00:00Z",
        "message": None,
    }


class TestRankItems:
    def test_sorts_by_engagement_total_and_truncates(self) -> None:
        items = [
            _item("low", {"score": 5}),
            _item("high", {"score": 100, "comments": 50}),
            _item("mid", {"score": 40}),
        ]
        ranked = rank_items(items, limit=2)
        assert [item["candidate_id"] for item in ranked] == ["high", "mid"]

    def test_ignores_non_numeric_and_bool_engagement(self) -> None:
        items = [
            _item("a", {"score": 10, "note": "n/a", "flag": True}),
            _item("b", {"score": 3}),
        ]
        ranked = rank_items(items)
        assert ranked[0]["candidate_id"] == "a"

    def test_drops_non_dict_entries(self) -> None:
        ranked = rank_items([_item("a", {"score": 1}), "junk", None])
        assert [item["candidate_id"] for item in ranked] == ["a"]

    def test_missing_engagement_counts_as_zero(self) -> None:
        item = _item("a", {})
        item.pop("engagement")
        assert rank_items([item])[0]["candidate_id"] == "a"


@pytest.mark.asyncio
class TestGetRanking:
    async def test_returns_empty_state_when_no_report(self) -> None:
        session = MagicMock()
        with patch(
            "app.last30days.service.Last30DaysReportStore"
        ) as store_cls:
            store_cls.return_value.get = AsyncMock(return_value=None)
            result = await get_ranking(session, "agent")

        assert result["direction"] == "agent"
        assert result["status"] == "no-results"
        assert result["items"] == []
        assert result["message"]

    async def test_returns_cached_report(self) -> None:
        report = MagicMock()
        report.status = "working"
        report.payload = {
            "items": [_item("a", {"score": 1})],
            "clusters": [],
            "sources": ["reddit"],
            "source_status": {"reddit": "ok"},
        }
        report.message = None
        report.fetched_at = datetime(2026, 8, 21, 0, 0, 0, tzinfo=UTC).replace(tzinfo=None)

        session = MagicMock()
        with patch("app.last30days.service.Last30DaysReportStore") as store_cls:
            store_cls.return_value.get = AsyncMock(return_value=report)
            result = await get_ranking(session, "skill")

        assert result["direction"] == "skill"
        assert result["status"] == "working"
        assert result["items"][0]["candidate_id"] == "a"
        assert result["sources"] == ["reddit"]
        assert result["fetched_at"] == datetime(2026, 8, 21, tzinfo=UTC).isoformat()

    async def test_degrades_when_table_missing(self) -> None:
        session = MagicMock()
        with patch("app.last30days.service.Last30DaysReportStore") as store_cls:
            store_cls.return_value.get = AsyncMock(side_effect=SQLAlchemyError("boom"))
            result = await get_ranking(session, "agent")

        assert result["status"] == "no-results"
        assert result["items"] == []
        assert "schema.sql" in result["message"]


@pytest.mark.asyncio
class TestRefreshRanking:
    async def test_ranks_and_persists_top_items(self) -> None:
        items = [_item(str(n), {"score": n}) for n in range(30)]
        engine = AsyncMock(return_value=_engine_result(items))
        session = MagicMock()
        session.commit = AsyncMock()

        with (
            patch("app.last30days.service.fetch_last30days", engine),
            patch("app.last30days.service.Last30DaysReportStore") as store_cls,
        ):
            store_cls.return_value.upsert = AsyncMock()
            result = await refresh_ranking(session, "agent")

        assert result["status"] == "working"
        assert len(result["items"]) == 20
        assert result["items"][0]["candidate_id"] == "29"
        engine.assert_awaited_once_with(query=DIRECTION_QUERIES["agent"], limit=100)
        store_cls.return_value.upsert.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_skips_persistence_on_engine_failure(self) -> None:
        engine = AsyncMock(
            return_value=_engine_result([])
            | {"status": "unconfigured", "message": "runtime missing"}
        )
        session = MagicMock()
        session.commit = AsyncMock()

        with (
            patch("app.last30days.service.fetch_last30days", engine),
            patch("app.last30days.service.Last30DaysReportStore") as store_cls,
        ):
            store_cls.return_value.upsert = AsyncMock()
            result = await refresh_ranking(session, "skill")

        assert result["status"] == "unconfigured"
        assert result["message"] == "runtime missing"
        store_cls.return_value.upsert.assert_not_called()
        session.commit.assert_not_called()

    async def test_returns_error_when_persistence_fails(self) -> None:
        engine = AsyncMock(return_value=_engine_result([_item("a", {"score": 1})]))
        session = MagicMock()
        session.commit = AsyncMock(side_effect=SQLAlchemyError("boom"))
        session.rollback = AsyncMock()

        with (
            patch("app.last30days.service.fetch_last30days", engine),
            patch("app.last30days.service.Last30DaysReportStore") as store_cls,
        ):
            store_cls.return_value.upsert = AsyncMock()
            result = await refresh_ranking(session, "agent")

        assert result["status"] == "error"
        assert "schema.sql" in result["message"]
        session.rollback.assert_awaited_once()

    async def test_rejects_unknown_direction(self) -> None:
        session = MagicMock()
        with pytest.raises(ValueError):
            await refresh_ranking(session, "mcp")
