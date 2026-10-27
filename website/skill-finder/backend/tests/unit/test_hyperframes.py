import json
from unittest.mock import Mock

import pytest

from app.core.config import Settings, settings
from app.daily import console, hyperframes, media, remotion, sample


def test_default_engine_routes_to_hyperframes_without_using_backup(monkeypatch, tmp_path):
    monkeypatch.delenv("DAILY_VIDEO_RENDERER", raising=False)
    configured = Settings(_env_file=None, database_url="sqlite:///test-only.db")
    assert configured.daily_video_renderer == "hyperframes"
    monkeypatch.setattr(settings, "daily_video_renderer", configured.daily_video_renderer)
    primary, backup = Mock(return_value=4), Mock()
    monkeypatch.setattr(hyperframes, "render", primary)
    monkeypatch.setattr(remotion, "render", backup)
    assert media.render([], "2026-10-26", tmp_path) == 4
    primary.assert_called_once()
    backup.assert_not_called()


def test_remotion_remains_an_explicit_backup_setting(monkeypatch, tmp_path):
    monkeypatch.delenv("DAILY_VIDEO_RENDERER", raising=False)
    environment = tmp_path / ".env"
    environment.write_text("DAILY_VIDEO_RENDERER=remotion\n")
    configured = Settings(_env_file=environment, database_url="sqlite:///test-only.db")
    monkeypatch.setattr(settings, "daily_video_renderer", configured.daily_video_renderer)
    primary, backup = Mock(), Mock(return_value=4)
    monkeypatch.setattr(hyperframes, "render", primary)
    monkeypatch.setattr(remotion, "render", backup)
    assert media.render([], "2026-10-26", tmp_path) == 4
    backup.assert_called_once()
    primary.assert_not_called()


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    renderer = tmp_path / "hyperframes-renderer"
    for package in ("producer", "engine"):
        dependency = renderer / "node_modules/@hyperframes" / package
        dependency.mkdir(parents=True)
        (dependency / "package.json").write_text("{}")
    monkeypatch.setattr(hyperframes, "RENDERER_DIR", renderer)
    monkeypatch.setattr(hyperframes.shutil, "which", lambda name: "node.exe")
    monkeypatch.setattr(settings, "hyperframes_browser_executable", "")
    return renderer


def test_hyperframes_uses_own_dependencies_and_explicit_tool_environment(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_ffmpeg_command", "custom-ffmpeg")
    monkeypatch.setattr(settings, "daily_ffprobe_command", "custom-ffprobe")
    monkeypatch.setattr(settings, "hyperframes_concurrency", 1)
    execute = Mock()
    monkeypatch.setattr(hyperframes, "run", execute)
    project = tmp_path / "version"
    hyperframes.invoke_renderer(tmp_path, check=True, template_project=project)
    args, kwargs = execute.call_args
    assert args[0] == ["node.exe", str(runtime / "scripts/render.mjs"),
                       str(tmp_path / "render-manifest.json"), "--check"]
    assert kwargs["env"]["HYPERFRAMES_TEMPLATE_DIR"] == str(project)
    assert kwargs["env"]["HYPERFRAMES_CONCURRENCY"] == "1"
    assert kwargs["env"]["HYPERFRAMES_FFMPEG_COMMAND"] == "custom-ffmpeg"
    assert kwargs["env"]["HYPERFRAMES_FFPROBE_COMMAND"] == "custom-ffprobe"
    assert not (runtime / "node_modules/remotion/package.json").exists()


def test_missing_hyperframes_dependency_fails_before_voice_or_fallback(runtime, tmp_path, monkeypatch):
    (runtime / "node_modules/@hyperframes/engine/package.json").unlink()
    prepare = Mock()
    fallback = Mock()
    monkeypatch.setattr(hyperframes, "prepare", prepare)
    monkeypatch.setattr(remotion, "render", fallback)
    monkeypatch.setattr(settings, "daily_video_renderer", "hyperframes")
    with pytest.raises(RuntimeError, match="HyperFrames dependencies missing"):
        media.render([], "2026-10-23", tmp_path)
    prepare.assert_not_called()
    fallback.assert_not_called()


def test_invalid_browser_fails_before_paid_voice(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "hyperframes_browser_executable", str(tmp_path / "missing.exe"))
    prepare = Mock()
    monkeypatch.setattr(hyperframes, "prepare", prepare)
    with pytest.raises(RuntimeError, match="HyperFrames browser missing"):
        hyperframes.render([], "2026-10-23", tmp_path)
    prepare.assert_not_called()


def test_absent_browser_on_path_fails_before_paid_voice(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_video_renderer", "hyperframes")
    monkeypatch.setattr(hyperframes.shutil, "which", lambda command:
                        "node.exe" if command == settings.daily_node_command else None)
    prepare = Mock()
    monkeypatch.setattr(hyperframes, "prepare", prepare)
    with pytest.raises(RuntimeError, match="HyperFrames browser missing"):
        hyperframes.render([], "2026-10-23", tmp_path)
    prepare.assert_not_called()
    assert next(item for item in console.runtime() if item["id"] == "renderer")["ready"] is False


def test_hyperframes_preserves_manifest_and_uses_shared_mastering(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(hyperframes, "ensure_tools", lambda: None)
    selected = (tmp_path / "version", {"accent": "#ffffff"}, "revision")
    monkeypatch.setattr("app.daily.templates.selection", lambda engine: selected)
    manifest = {"scenes": [{"durationInFrames": 120}], "music": {"file": "music.wav"}}

    def prepare(scenes, day, directory, assets, *, template_selection):
        assert template_selection() == selected
        return manifest

    def invoke(directory, **kwargs):
        assert kwargs["template_project"] == selected[0]
        assert not (directory / "render-result.json").exists()
        (directory / "render-raw-result.json").write_text(json.dumps({
            "duration_seconds": 4, "width": 1080, "height": 1920, "fps": 30,
        }))

    def master(directory, duration, *, music):
        assert duration == 4 and music == manifest["music"]
        assert json.loads((directory / "render-progress.json").read_text())["phase"] == "mastering"
        assert not (directory / "render-result.json").exists()
        return {"media": {"verified": True}}

    monkeypatch.setattr(hyperframes, "prepare", prepare)
    monkeypatch.setattr(hyperframes, "invoke_renderer", invoke)
    monkeypatch.setattr(hyperframes, "master_video", master)
    assert hyperframes.render([], "2026-10-23", tmp_path) == 4
    result = json.loads((tmp_path / "render-result.json").read_text())
    assert result["renderer"] == "hyperframes"
    assert result["audio_mastering"]["media"]["verified"] is True
    assert not (tmp_path / "render-raw-result.json").exists()
    assert json.loads((tmp_path / "render-progress.json").read_text())["phase"] == "completed"


def test_hyperframes_verification_failure_never_marks_sample_ready(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(hyperframes, "ensure_tools", lambda: None)
    monkeypatch.setattr("app.daily.templates.selection", lambda engine: (tmp_path, {}, "revision"))
    monkeypatch.setattr(hyperframes, "prepare", lambda *args, **kwargs: {
        "scenes": [{"durationInFrames": 120}],
    })

    def invoke(directory, **kwargs):
        (directory / "render-raw-result.json").write_text('{"duration_seconds": 4}')

    monkeypatch.setattr(hyperframes, "invoke_renderer", invoke)
    monkeypatch.setattr(hyperframes, "master_video", Mock(side_effect=RuntimeError("verification failed")))
    (tmp_path / "render-result.json").write_text('{"old": true}')
    with pytest.raises(RuntimeError, match="verification failed"):
        hyperframes.render([], "2026-10-23", tmp_path)
    assert not (tmp_path / "render-result.json").exists()
    assert json.loads((tmp_path / "render-progress.json").read_text())["phase"] == "failed"


def test_hyperframes_sample_uses_selected_engine_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "daily_video_renderer", "hyperframes")
    monkeypatch.setattr(sample.store, "root", lambda: tmp_path / "reports")
    calls = []
    monkeypatch.setattr(hyperframes, "invoke_renderer", lambda directory, **kwargs: calls.append((directory, kwargs)))

    def render(scenes, day, directory, sources):
        assert scenes[1]["heading"] == "heygen-com/hyperframes"
        assert "HTML" in scenes[1]["summary"]
        assert "Remotion" not in json.dumps(scenes)
        assert json.loads((sources / "heygen-com--hyperframes.json").read_text())["file"] == "demo.mp4"
        assert calls == [(sources, {"demo": True})]
        return 30

    monkeypatch.setattr(hyperframes, "render", render)
    assert sample.generate_sample()["renderer"] == "hyperframes"


def test_hyperframes_console_shows_real_engine_without_remotion(runtime, monkeypatch):
    monkeypatch.setattr(settings, "daily_video_renderer", "hyperframes")
    monkeypatch.setattr(settings, "daily_tts_provider", "mimo")
    monkeypatch.setattr(settings, "mimo_api_key", type(settings.mimo_api_key)("private-test-key"))
    values = {item["id"]: item for item in console.runtime()}
    assert values["renderer"]["ready"] is True
    assert "HyperFrames" in values["renderer"]["value"]
    assert "双遍" in values["ffmpeg"]["value"]
    assert values["tts"]["value"] == "mimo"
    assert "Whisper" in values["captions"]["value"]
    assert "private-test-key" not in json.dumps(values)
    metadata = console.template_metadata()
    assert metadata["engine"] == "hyperframes"
    assert metadata["directory"].endswith("hyperframes-renderer")
    assert {item["path"] for item in metadata["files"]} == {"src/template.html", "src/demo.html"}


def test_legacy_sample_requires_explicit_modern_engine(monkeypatch):
    monkeypatch.setattr(settings, "daily_video_renderer", "legacy")
    with pytest.raises(RuntimeError, match="Engine samples require"):
        sample.generate_sample()
