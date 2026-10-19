import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.daily import store, templates
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path / "reports"))
    monkeypatch.setattr(settings, "admin_key", type(settings.admin_key)("template-test-only"))
    def compile_ok(args, **kwargs):
        project = Path(args[-1])
        (project / "preview").mkdir()
        (project / "preview/app.js").write_text("/* isolated unit compilation */")
        (project / "diagnostics.json").write_text('{"ok":true,"diagnostics":[]}')
        return ""
    monkeypatch.setattr(templates, "run", compile_ok)
    monkeypatch.setattr(templates.shutil, "which", lambda command: "node")
    monkeypatch.setattr("app.daily.remotion.invoke_renderer", lambda *args, **kwargs: None)
    return templates.document()


def body(document):
    return {"expected_revision": document["revision"], "theme": document["theme"],
            "sources": {file["path"]: file["code"] for file in document["sources"] if file["editable"]}}


def client():
    return TestClient(app, base_url="http://localhost")


def test_source_requires_admin_and_disallows_arbitrary_file_writes(workspace):
    assert client().get("/api/v1/daily-reports/template").status_code == 401
    draft = body(workspace)
    draft["sources"]["../../.env"] = "unwanted-write"
    response = client().put("/api/v1/daily-reports/template", json=draft,
                            headers={"X-Admin-Key": "template-test-only"})
    assert response.status_code == 422
    assert not (templates.root() / "active.json").exists()


def test_draft_enforces_size_and_style_boundaries(workspace):
    draft = body(workspace)
    draft["sources"]["src/video.tsx"] = "x" * (128 * 1024 + 1)
    with pytest.raises(ValidationError):
        templates.Draft.model_validate(draft)
    draft = body(workspace)
    draft["theme"] = {**draft["theme"], "accent": "url(https://remote.example/image)"}
    with pytest.raises(ValidationError):
        templates.Draft.model_validate(draft)


def test_compilation_failure_keeps_active_template_and_returns_positions(workspace, monkeypatch):
    def fail(args, **kwargs):
        project = Path(args[-1])
        (project / "diagnostics.json").write_text(json.dumps({"ok": False, "diagnostics": [
            {"file": "src/video.tsx", "line": 12, "column": 3, "message": "Syntax error"},
        ]}))
    monkeypatch.setattr(templates, "run", fail)
    response = client().put("/api/v1/daily-reports/template", json=body(workspace),
                            headers={"X-Admin-Key": "template-test-only"})
    assert response.status_code == 422
    assert response.json()["diagnostics"][0]["line"] == 12
    assert templates.document()["revision"] == workspace["revision"]


def test_runtime_failure_never_activates_draft(workspace, monkeypatch):
    monkeypatch.setattr("app.daily.remotion.invoke_renderer", Mock(side_effect=RuntimeError("runtime failure")))
    draft = body(workspace)
    draft["theme"] = {**draft["theme"], "brand": "修改后的栏目"}
    with pytest.raises(RuntimeError):
        templates.save(templates.Draft.model_validate(draft))
    assert templates.document()["revision"] == workspace["revision"]


def test_save_restore_are_versioned_and_never_change_approved_media(workspace):
    report = {"date": "2026-10-19", "status": "approved", "script": "已审核口播", "caption": "已审核文案"}
    store.save(report)
    video = store.report_dir(report["date"]) / "video.mp4"
    video.write_bytes(b"approved immutable video")
    draft = body(workspace)
    draft["theme"] = {**draft["theme"], "brand": "我的栏目"}
    draft["sources"]["src/video.tsx"] += "\n// 本次自定义模板\n"
    saved = templates.save(templates.Draft.model_validate(draft))
    assert saved["revision"] != workspace["revision"]
    assert templates.selection()[0] == templates.root() / "versions" / saved["revision"]
    assert templates.selection()[1]["brand"] == "我的栏目"
    assert "本次自定义模板" in (templates.selection()[0] / "src/video.tsx").read_text(encoding="utf-8")
    assert video.read_bytes() == b"approved immutable video"
    assert store.load(report["date"]) == report
    restored = templates.restore(workspace["revision"], saved["revision"])
    assert restored["revision"] == workspace["revision"]
    assert len(restored["versions"]) == 2


def test_conflict_fails_before_compiling(workspace, monkeypatch):
    compile_run = Mock()
    monkeypatch.setattr(templates, "run", compile_run)
    draft = body(workspace)
    draft["expected_revision"] = "0" * 64
    response = client().put("/api/v1/daily-reports/template", json=draft,
                            headers={"X-Admin-Key": "template-test-only"})
    assert response.status_code == 409
    compile_run.assert_not_called()


def test_preview_serves_only_bundle_and_frozen_media(workspace):
    project, metadata = templates.compile_draft(templates.Draft.model_validate(body(workspace)))
    base = "/api/v1/daily-reports/template/previews/" + metadata["id"]
    response = client().get(base + "/app.js")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert client().get(base + "/src/video.tsx").status_code == 404
    assert client().get(base + "/preview.json").status_code == 404
    assert (project / "src/video.tsx").is_file()
