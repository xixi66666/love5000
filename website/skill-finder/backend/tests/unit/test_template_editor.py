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
    monkeypatch.setattr(settings, "daily_video_renderer", "remotion")
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


@pytest.fixture
def hyperframes_workspace(workspace, tmp_path, monkeypatch):
    renderer = tmp_path / "hyperframes-renderer"
    (renderer / "src").mkdir(parents=True)
    for name in ("template.html", "demo.html"):
        (renderer / "src" / name).write_text('<!doctype html><div>HyperFrames</div>', encoding="utf-8")
    (renderer / "src/template-defaults.json").write_text(json.dumps(workspace["theme"]), encoding="utf-8")
    monkeypatch.setattr(templates, "HYPERFRAMES_RENDERER", renderer)
    return templates.document("hyperframes")


def body(document):
    return {"engine": document.get("engine", "remotion"),
            "expected_revision": document["revision"], "theme": document["theme"],
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


def test_hyperframes_has_separate_sources_and_preview_capability(hyperframes_workspace, workspace):
    response = client().get("/api/v1/daily-reports/template?engine=hyperframes",
                            headers={"X-Admin-Key": "template-test-only"})
    assert response.status_code == 200
    assert response.json()["engine"] == "hyperframes"
    assert {item["path"] for item in response.json()["sources"]} == {"src/template.html", "src/demo.html"}
    project, metadata = templates.compile_draft(templates.Draft.model_validate(body(hyperframes_workspace)))
    assert project.parent.parent == templates.root("hyperframes")
    base = "/api/v1/daily-reports/template/engines/hyperframes/previews/" + metadata["id"]
    preview = client().get(base + "/index.html")
    assert preview.status_code == 200
    assert "script-src" in preview.headers["content-security-policy"]
    assert "script-src 'unsafe-inline'" not in preview.headers["content-security-policy"]
    assert client().get(base + "/app.js").status_code == 200
    assert client().get(base + "/src/template.html").status_code == 404
    assert client().get(base.replace("/engines/hyperframes", "") + "/app.js").status_code == 404
    assert templates.document("remotion")["revision"] == workspace["revision"]


def test_drafts_cannot_reuse_files_from_another_engine(hyperframes_workspace, workspace):
    draft = body(hyperframes_workspace)
    draft["sources"] = body(workspace)["sources"]
    with pytest.raises(ValidationError):
        templates.Draft.model_validate(draft)
    draft = body(hyperframes_workspace)
    draft.pop("engine")
    with pytest.raises(ValidationError):
        templates.Draft.model_validate(draft)
    draft = body(hyperframes_workspace)
    draft["sources"]["package.json"] = '{"scripts":{"build":"bad command"}}'
    with pytest.raises(ValidationError):
        templates.Draft.model_validate(draft)


def test_legacy_remotion_metadata_remains_readable(workspace):
    project, theme, revision = templates.selection("remotion")
    templates.store_version(project, theme, revision)
    version_path = templates.root("remotion") / "versions" / revision / "version.json"
    version = json.loads(version_path.read_text(encoding="utf-8"))
    version.pop("engine")
    templates.json_write(version_path, version)
    templates.json_write(templates.root("remotion") / "active.json", {"revision": revision})
    assert templates.selection("remotion")[2] == workspace["revision"]


def test_engine_binding_prevents_cross_engine_restore(hyperframes_workspace, workspace):
    project, theme, revision = templates.selection("remotion")
    templates.store_version(project, theme, revision)
    with pytest.raises(FileNotFoundError):
        templates.restore(revision, hyperframes_workspace["revision"], "hyperframes")
    assert not (templates.root("hyperframes") / "active.json").exists()


def test_hyperframes_save_checks_the_selected_renderer_and_keeps_remotion_version(
    hyperframes_workspace, workspace, monkeypatch,
):
    check = Mock()
    remotion_check = Mock(side_effect=AssertionError("Wrong renderer"))
    monkeypatch.setattr("app.daily.hyperframes.invoke_renderer", check)
    monkeypatch.setattr("app.daily.remotion.invoke_renderer", remotion_check)
    draft = body(hyperframes_workspace)
    draft["sources"]["src/template.html"] += "\n<!-- 自定义 HTML -->"
    saved = templates.save(templates.Draft.model_validate(draft))
    assert saved["engine"] == "hyperframes"
    assert saved["revision"] != hyperframes_workspace["revision"]
    check.assert_called_once()
    assert check.call_args.kwargs["check"] is True
    assert check.call_args.kwargs["template_project"] == check.call_args.args[0]
    assert not (templates.root("remotion") / "active.json").exists()
    assert templates.selection("remotion")[2] == workspace["revision"]
    active = json.loads((templates.root("hyperframes") / "active.json").read_text(encoding="utf-8"))
    assert active["engine"] == "hyperframes"
    restored = templates.restore(hyperframes_workspace["revision"], saved["revision"], "hyperframes")
    assert restored["revision"] == hyperframes_workspace["revision"]


def test_stale_preview_revision_is_rejected_before_compilation(hyperframes_workspace, monkeypatch):
    run = Mock()
    monkeypatch.setattr(templates, "run", run)
    draft = body(hyperframes_workspace)
    draft["expected_revision"] = "0" * 64
    response = client().post("/api/v1/daily-reports/template/preview", json=draft,
                             headers={"X-Admin-Key": "template-test-only"})
    assert response.status_code == 409
    run.assert_not_called()
