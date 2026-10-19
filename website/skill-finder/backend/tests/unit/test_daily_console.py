import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from PIL import Image

from app.core.config import settings
from app.daily import store
from app.daily.console import snapshot
from app.daily.progress import Tracker, current, now, tracking
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path / "reports"))
    monkeypatch.setattr(settings, "daily_assets_dir", str(tmp_path / "assets"))
    monkeypatch.setattr(settings, "admin_key", type(settings.admin_key)("console-test-only"))
    monkeypatch.setattr(settings, "daily_qq_target", "")
    report = {"date": now()[:10], "status": "failed", "items": [
        {"full_name": "org/demo", "rank": 1, "summary": "实际用途。", "url": "https://github.com/org/demo", "daily_stars": 5},
    ]}
    store.save(report)
    return report


def client():
    return TestClient(app, base_url="http://localhost")


def test_failed_stage_is_durable_and_sanitized(workspace):
    with pytest.raises(RuntimeError), tracking(workspace["date"]) as progress:
        progress.finish("collection", "采集结束。")
        progress.begin("voice", "正在配音。", total=3)
        progress.tick("voice", "第一段完成。")
        raise RuntimeError("private-key-and-upstream-body")
    saved = Tracker(workspace["date"]).data
    voice = next(stage for stage in saved["stages"] if stage["id"] == "voice")
    assert voice["status"] == "failed"
    assert voice["done"] == 1 and voice["total"] == 3
    assert "private-key" not in json.dumps(saved)
    assert current() is None


def test_legacy_history_has_no_invented_progress(workspace):
    workspace["status"] = "pending_review"
    store.save(workspace)
    value = snapshot(workspace["date"])
    assert value["recorded"] is False
    assert all(stage["status"] == "untracked" for stage in value["workflow"]["stages"][:7])
    assert value["workflow"]["stages"][7]["status"] == "waiting"


def test_stopped_generation_is_recoverable(workspace):
    from datetime import datetime

    workspace["status"] = "generating"
    store.save(workspace)
    progress = Tracker(workspace["date"])
    progress.begin("render", "正在渲染。")
    progress.data["updated_at"] = (datetime.fromisoformat(now()) - timedelta(minutes=2)).isoformat()
    (store.report_dir(workspace["date"]) / "workflow.json").write_text(json.dumps(progress.data))
    assert snapshot(workspace["date"])["status"] == "interrupted"


def test_console_only_returns_safe_environment_metadata(workspace, monkeypatch):
    monkeypatch.setattr(settings, "mimo_api_key", type(settings.mimo_api_key)("private-tts-value"))
    monkeypatch.setattr(settings, "daily_whisper_model", "C:/private/models/small")
    response = client().get("/api/v1/daily-reports/console", params={"day": workspace["date"]})
    assert response.status_code == 200
    assert "private-tts-value" not in response.text
    assert "C:/private" not in response.text
    assert response.json()["assets"][0]["status"] == "missing"


def test_generation_rejects_duplicate_dispatch(workspace):
    with FileLock(str(store.root() / ".dispatch.lock"), timeout=0):
        response = client().post("/api/v1/daily-reports/generate", headers={"X-Admin-Key": "console-test-only"})
    assert response.status_code == 409


def test_generation_cannot_overwrite_reviewed_report(workspace, monkeypatch):
    workspace["status"] = "pending_review"
    store.save(workspace)
    task = AsyncMock()
    monkeypatch.setattr("app.api.v1.daily_reports.task", task)
    response = client().post("/api/v1/daily-reports/generate", headers={"X-Admin-Key": "console-test-only"})
    assert response.status_code == 409
    task.assert_not_called()


def test_upload_checks_authentication_and_actual_image(workspace):
    url = f"/api/v1/daily-reports/{workspace['date']}/assets/org/demo"
    params = {"filename": "demo.png", "source": "https://github.com/org/demo"}
    assert client().put(url, params=params, content=b"invalid").status_code == 401
    headers = {"X-Admin-Key": "console-test-only", "Content-Type": "application/octet-stream"}
    assert client().put(url, params=params, headers=headers, content=b"invalid").status_code == 422
    image = io.BytesIO()
    Image.new("RGB", (20, 20)).save(image, format="PNG")
    assert client().put(url, params=params, headers=headers, content=image.getvalue()).status_code == 200
    assert snapshot(workspace["date"])["assets"][0]["status"] == "ready"
    root = settings.daily_assets_dir
    manifest = json.loads((Path(root) / "org--demo.json").read_text())
    assert manifest["file"].endswith(".png")
    # 后续坏文件不能破坏已经校验过的素材。
    assert client().put(url, params=params, headers=headers, content=b"bad").status_code == 422
    assert snapshot(workspace["date"])["assets"][0]["status"] == "ready"


def test_upload_rejects_oversize_without_changing_assets(workspace, monkeypatch):
    monkeypatch.setattr("app.daily.assets.MAX_ASSET_BYTES", 3)
    response = client().put(
        f"/api/v1/daily-reports/{workspace['date']}/assets/org/demo",
        params={"filename": "demo.png", "source": "https://github.com/org/demo"},
        headers={"X-Admin-Key": "console-test-only"}, content=b"1234",
    )
    assert response.status_code == 413
    assert not list(Path(settings.daily_assets_dir).glob("*"))


def test_sample_downloads_never_expose_work_files(workspace, tmp_path):
    directory = tmp_path / "video-samples" / "20261019-150000"
    directory.mkdir(parents=True)
    (directory / "video.mp4").write_bytes(b"sample")
    (directory / "render-manifest.json").write_text('{"private":"work"}')
    assert client().get("/api/v1/daily-reports/samples/20261019-150000/files/video.mp4").status_code == 200
    assert client().get("/api/v1/daily-reports/samples/20261019-150000/files/render-manifest.json").status_code == 404
