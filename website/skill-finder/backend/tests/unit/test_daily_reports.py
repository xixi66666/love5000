import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import compose, generate, summarize
from app.main import app


def client():
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def daily(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path))
    monkeypatch.setattr(settings, "admin_key", type(settings.admin_key)("test-review-key"))
    report = {
        "date": "2026-10-18", "status": "pending_review", "title": "Test daily",
        "script": "Original narration", "caption": "Original caption", "items": [],
    }
    directory = store.report_dir(report["date"])
    directory.mkdir()
    (directory / "video.mp4").write_bytes(b"the reviewed video")
    report["video_sha256"] = store.digest(directory / "video.mp4")
    report["review_digest"] = store.approval_digest(report)
    store.save(report)
    return report


def test_review_requires_authentication(daily):
    response = client().post(
        "/api/v1/daily-reports/2026-10-18/review",
        json={"decision": "approve", "expected_digest": daily["review_digest"]},
    )
    assert response.status_code == 401
    assert store.load(daily["date"])["status"] == "pending_review"


def test_approval_is_bound_to_video_and_caption(daily, monkeypatch):
    from app.api.v1 import daily_reports

    publish = AsyncMock()
    monkeypatch.setattr(daily_reports, "task", publish)
    response = client().post(
        "/api/v1/daily-reports/2026-10-18/review",
        headers={"X-Admin-Key": "test-review-key"},
        json={"decision": "approve", "expected_digest": daily["review_digest"]},
    )
    assert response.status_code == 200
    approved = store.load(daily["date"])
    assert store.verify_approval(approved)
    approved["caption"] = "unreviewed replacement"
    assert not store.verify_approval(approved)
    approved["caption"] = daily["caption"]
    (store.report_dir(daily["date"]) / "video.mp4").write_bytes(b"replaced")
    assert not store.verify_approval(approved)
    publish.assert_awaited_once_with("publish", daily["date"])


def test_modified_video_cannot_be_approved(daily):
    (store.report_dir(daily["date"]) / "video.mp4").write_bytes(b"modified")
    response = client().post(
        "/api/v1/daily-reports/2026-10-18/review",
        headers={"X-Admin-Key": "test-review-key"},
        json={"decision": "approve", "expected_digest": daily["review_digest"]},
    )
    assert response.status_code == 409


def test_unapproved_report_never_enters_publisher(daily):
    response = client().post(
        "/api/v1/daily-reports/2026-10-18/publish", headers={"X-Admin-Key": "test-review-key"},
    )
    assert response.status_code == 409


def test_administration_is_rejected_over_public_plaintext_http(daily):
    response = TestClient(app, base_url="http://49.232.128.132").post(
        "/api/v1/daily-reports/2026-10-18/publish", headers={"X-Admin-Key": "test-review-key"},
    )
    assert response.status_code == 403


def test_login_screen_is_private(daily):
    response = client().get("/api/v1/daily-reports/publisher/login/screen")
    assert response.status_code == 401


def test_cron_retry_never_replaces_report_under_review(daily, monkeypatch):
    monkeypatch.setattr("app.daily.pipeline.now", lambda: "2026-10-18T08:00:00+08:00")
    prepare = AsyncMock(side_effect=AssertionError("A reviewed draft is immutable"))
    monkeypatch.setattr("app.daily.pipeline.prepare", prepare)
    assert generate(collect=True) == daily
    prepare.assert_not_awaited()


def test_rejection_does_not_start_publisher(daily, monkeypatch):
    from app.api.v1 import daily_reports

    publish = AsyncMock()
    monkeypatch.setattr(daily_reports, "task", publish)
    response = client().post(
        "/api/v1/daily-reports/2026-10-18/review",
        headers={"X-Admin-Key": "test-review-key"},
        json={"decision": "reject", "expected_digest": daily["review_digest"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    publish.assert_not_awaited()


def test_generation_without_fresh_ranking_fails_instead_of_faking_top10(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path))
    monkeypatch.setattr("app.daily.pipeline.candidates", AsyncMock(return_value=[]))
    with pytest.raises(RuntimeError, match="No fresh"):
        generate()
    report_file = next(tmp_path.glob("*/report.json"))
    assert json.loads(report_file.read_text())["status"] == "failed"


def test_countdown_and_honest_count():
    items = [
        {"rank": 1, "full_name": "org/first", "daily_stars": 12, "summary": "工具一。"},
        {"rank": 2, "full_name": "org/second", "daily_stars": 10, "summary": "工具二。"},
    ]
    title, scenes = compose(items, "2026-10-18")
    assert "Top 2" in title
    assert scenes[1]["heading"] == "org/second"
    assert scenes[2]["heading"] == "org/first"
    assert summarize('{"introduction":"实际用途。"}', "English") == "实际用途。"


def test_collection_and_report_query_share_one_database_event_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path))
    loops = []

    async def collect():
        loops.append(asyncio.get_running_loop())

    async def read_candidates(day):
        assert asyncio.get_running_loop() is loops[0]
        return [{
            "rank": 1, "full_name": "org/demo", "url": "https://github.com/org/demo",
            "summary": "真实用途。", "daily_stars": 10, "total_stars": 100,
            "snapshot_at": "2026-10-19T00:00:00Z",
        }]

    def render(scenes, day, directory):
        (directory / "video.mp4").write_bytes(b"rendered sample")
        return 5

    monkeypatch.setattr("app.core.scheduler._scheduled_collection", collect)
    monkeypatch.setattr("app.daily.pipeline.candidates", read_candidates)
    monkeypatch.setattr("app.daily.pipeline.render", render)
    assert generate(collect=True)["status"] == "pending_review"


@pytest.mark.parametrize("day", ["../private", "2026-13-40", "2026-1-1"])
def test_report_path_validation(day):
    with pytest.raises(ValueError):
        store.report_dir(day)
