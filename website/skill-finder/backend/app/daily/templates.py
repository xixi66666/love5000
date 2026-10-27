"""模板草稿、编译与不可变版本；不允许网页写任意工程文件。"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.daily import store
from app.daily.media import run
from app.daily.progress import now

RENDERER = Path(__file__).resolve().parents[3] / "video-renderer"
EDITABLE = ("src/video.tsx", "src/demo.tsx", "src/types.ts")
SOURCE_FILES = (*EDITABLE, "src/root.tsx", "src/index.ts", "src/editor-preview.tsx", "src/template-defaults.json")
Engine = Literal["remotion", "hyperframes"]
HYPERFRAMES_RENDERER = RENDERER.parent / "hyperframes-renderer"


def engine_name(engine: Engine | None = None) -> Engine:
    value = engine or ("hyperframes" if settings.daily_video_renderer == "hyperframes" else "remotion")
    if value not in {"remotion", "hyperframes"}:
        raise ValueError("Unsupported template engine")
    return value


def descriptor(engine: Engine | None = None) -> dict:
    value = engine_name(engine)
    editable = ("src/template.html", "src/demo.html") if value == "hyperframes" else EDITABLE
    return {"engine": value, "label": "HyperFrames" if value == "hyperframes" else "Remotion",
            "editable": editable, "sources": (*editable, "src/template-defaults.json")
            if value == "hyperframes" else SOURCE_FILES,
            "renderer": HYPERFRAMES_RENDERER if value == "hyperframes" else RENDERER}


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accent: str = Field(pattern=r"^#[a-fA-F0-9]{6}$")
    background: str = Field(pattern=r"^#[a-fA-F0-9]{6}$")
    foreground: str = Field(pattern=r"^#[a-fA-F0-9]{6}$")
    brand: str = Field(min_length=1, max_length=24)
    tagline: str = Field(min_length=1, max_length=32)
    headlineSize: int = Field(ge=48, le=100)
    captionSize: int = Field(ge=28, le=68)
    captionBottom: int = Field(ge=220, le=420)
    safeRight: int = Field(ge=96, le=220)
    mediaTop: int = Field(ge=540, le=700)
    motion: float = Field(ge=0, le=1.5)


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # 老客户端未带引擎时固定使用 Remotion，不随运行配置隐式写入另一引擎。
    engine: Engine = "remotion"
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: dict[str, str]
    theme: Theme

    @model_validator(mode="after")
    def allowed_sources(self):
        if set(self.sources) != set(descriptor(self.engine)["editable"]):
            raise ValueError("Only the engine's editable template files are accepted")
        if any(not text.strip() or len(text.encode("utf-8")) > 128 * 1024 for text in self.sources.values()):
            raise ValueError("Template files must contain 1..128 KiB of source")
        return self


class CompilationError(Exception):
    def __init__(self, diagnostics: list[dict]):
        self.diagnostics = diagnostics
        super().__init__("Template did not pass validation")


def root(engine: Engine | None = None) -> Path:
    directory = store.root().parent / "video-template"
    # 保留既有 active.json/versions 路径；新引擎的版本始终隔离。
    if engine_name(engine) == "hyperframes":
        directory /= "hyperframes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def sources(project: Path, engine: Engine = "remotion") -> dict[str, str]:
    return {name: (project / name).read_text(encoding="utf-8") for name in descriptor(engine)["sources"]}


def fingerprint(files: dict[str, str], theme: dict, engine: Engine = "remotion") -> str:
    # Remotion 保留旧摘要算法，以兼容现存不可变版本。
    content = {"sources": files, "theme": theme}
    if engine != "remotion":
        content["engine"] = engine
    value = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def selection(engine: Engine | None = None) -> tuple[Path, dict, str]:
    engine = engine_name(engine)
    renderer = descriptor(engine)["renderer"]
    try:
        active = json.loads((root(engine) / "active.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        files = sources(renderer, engine)
        theme = json.loads(files["src/template-defaults.json"])
        Theme.model_validate(theme)
        return renderer, theme, fingerprint(files, theme, engine)
    if active.get("engine", "remotion") != engine:
        raise ValueError("Template engine does not match active version")
    revision = active["revision"]
    if not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise ValueError("Invalid active template revision")
    project = root(engine) / "versions" / revision
    metadata = json.loads((project / "version.json").read_text(encoding="utf-8"))
    if metadata.get("engine", "remotion") != engine:
        raise ValueError("Template engine does not match version")
    theme = metadata["theme"]
    Theme.model_validate(theme)
    if fingerprint(sources(project, engine), theme, engine) != revision:
        raise ValueError("Template version contents changed")
    return project, theme, revision


def document(engine: Engine | None = None) -> dict:
    engine = engine_name(engine)
    spec = descriptor(engine)
    project, theme, revision = selection(engine)
    versions = []
    for filename in (root(engine) / "versions").glob("*/version.json"):
        metadata = json.loads(filename.read_text(encoding="utf-8"))
        if metadata.get("engine", "remotion") == engine:
            versions.append({"revision": filename.parent.name, "created_at": metadata["created_at"], "engine": engine})
    labels = {"accent": "强调色", "background": "画面背景", "foreground": "文字与面板", "brand": "栏目名称",
              "tagline": "栏目短句", "headlineSize": "标题字号", "captionSize": "字幕字号", "captionBottom": "字幕距底部",
              "safeRight": "右侧安全区", "mediaTop": "素材距顶部", "motion": "入场动效强度"}
    fields = []
    for key, schema in Theme.model_json_schema()["properties"].items():
        kind = "color" if key in {"accent", "background", "foreground"} else "text" if schema["type"] == "string" else "number"
        fields.append({"key": key, "label": labels[key], "kind": kind, "min": schema.get("minimum"),
                       "max": schema.get("maximum"), "step": 0.1 if key == "motion" else 1,
                       "maxLength": schema.get("maxLength")})
    visible = spec["editable"] if engine == "hyperframes" else (*EDITABLE, "src/root.tsx")
    return {"engine": engine, "engine_label": spec["label"], "current_engine": settings.daily_video_renderer,
            "revision": revision, "theme": theme, "fields": fields,
            "defaults": json.loads((spec["renderer"] / "src/template-defaults.json").read_text(encoding="utf-8")),
            "sources": [{"path": name, "code": (project / name).read_text(encoding="utf-8"),
                         "editable": name in spec["editable"]} for name in visible],
            "versions": sorted(versions, key=lambda item: item["created_at"], reverse=True)[:30]}


def copy_project(project: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def preview_props(project: Path) -> dict:
    """仅复制清单内的音视频与字体，不托管整个日报目录。"""
    manifests = sorted((store.root().parent / "video-samples").glob("*/render-manifest.json"), reverse=True)
    if not manifests:
        manifests = sorted(store.root().glob("????-??-??/render-manifest.json"), reverse=True)
    if not manifests:
        return {"day": "模板预览 · 示例内容", "scenes": [{"label": "TOOL CHECK", "heading": "今天的工具，先看效果。",
                "summary": "这是模板开发示例，正式内容由日报流程提供。", "narration": "", "durationInFrames": 240,
                "captions": [{"text": "在操作台里修改模板，实时预览。", "start": 0.5, "end": 7.5}]}]}
    manifest = manifests[0]
    original = json.loads(manifest.read_text(encoding="utf-8"))
    base = manifest.parent.resolve()
    media = project / "preview" / "media"
    media.mkdir(parents=True, exist_ok=True)
    copied = {}

    def freeze(name):
        source = (base / name).resolve()
        if not source.is_relative_to(base) or not source.is_file() or source.suffix.lower() not in {
            ".wav", ".mp3", ".mp4", ".png", ".jpg", ".jpeg", ".ttc", ".ttf",
        }:
            raise ValueError("Invalid preview media")
        if source not in copied:
            target = media / (str(len(copied)) + source.suffix.lower())
            shutil.copyfile(source, target)
            copied[source] = "media/" + target.name
        return copied[source]

    for scene in original["scenes"]:
        if scene.get("audio"):
            scene["audio"] = freeze(scene["audio"])
        if scene.get("asset"):
            scene["asset"]["src"] = freeze(scene["asset"]["src"])
    if original.get("font"):
        original["font"] = freeze(original["font"])
    original["day"] = "模板预览 · 非本期日榜"
    return original


def compile_draft(body: Draft) -> tuple[Path, dict]:
    engine = body.engine
    spec = descriptor(engine)
    # 仅清理本模块生成的旧预览缓存；模板版本和日报目录不参与清理。
    cache = (root(engine) / "previews").resolve()
    previous = sorted((path for path in cache.glob("*") if re.fullmatch(r"[a-f0-9]{32}", path.name)
                       and path.is_dir() and not path.is_symlink()), key=lambda path: path.stat().st_mtime, reverse=True)
    for obsolete in previous[11:]:
        target = obsolete.resolve()
        if target.parent == cache:
            shutil.rmtree(target)
    base, _, revision = selection(engine)
    if revision != body.expected_revision:
        raise FileExistsError("Template changed")
    files = sources(base, engine)
    files.update(body.sources)
    # 预览桥接代码始终来自可信工程，不允许草稿替换其消息协议。
    if engine == "remotion":
        files["src/editor-preview.tsx"] = (RENDERER / "src/editor-preview.tsx").read_text(encoding="utf-8")
    project = root(engine) / "previews" / uuid4().hex
    copy_project(project, files)
    node = shutil.which(settings.daily_node_command)
    if not node:
        raise RuntimeError("Node is not configured")
    renderer = spec["renderer"]
    run([node, str(renderer / "scripts/build-editor.mjs"), str(project)], cwd=renderer, timeout=90)
    diagnostics = json.loads((project / "diagnostics.json").read_text(encoding="utf-8"))
    if not diagnostics["ok"]:
        raise CompilationError(diagnostics["diagnostics"])
    props = preview_props(project)
    props["theme"] = body.theme.model_dump()
    revision = fingerprint(files, props["theme"], engine)
    metadata = {"engine": engine, "id": project.name, "revision": revision, "created_at": now(), "props": props}
    json_write(project / "preview.json", metadata)
    (project / "preview/index.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>模板预览</title>'
        '<style>html,body,#root{margin:0;width:100%;height:100%;background:#101618;color:#eee;'
        'font-family:system-ui}*{box-sizing:border-box}</style><div id="root"></div>'
        '<script src="app.js" defer></script></html>', encoding="utf-8",
    )
    return project, metadata


def store_version(project: Path, theme: dict, revision: str, engine: Engine = "remotion") -> None:
    target = root(engine) / "versions" / revision
    if not (target / "version.json").is_file():
        copy_project(target, sources(project, engine))
        json_write(target / "version.json", {"engine": engine, "created_at": now(), "theme": theme})


def save(body: Draft) -> dict:
    engine = body.engine
    base, previous_theme, previous_revision = selection(engine)
    if previous_revision != body.expected_revision:
        raise FileExistsError("Template changed")
    project, metadata = compile_draft(body)
    # 保存前通过所选引擎真正渲染一帧；不调用配音或发布。
    manifest = json.loads(json.dumps(metadata["props"]))
    for scene in manifest["scenes"]:
        if scene.get("audio"):
            scene["audio"] = "preview/" + scene["audio"]
        else:
            # 开发占位分镜没有配音，预览校验允许此分镜不提供音轨。
            scene["audio"] = None
        if scene.get("asset"):
            scene["asset"]["src"] = "preview/" + scene["asset"]["src"]
    if manifest.get("font"):
        manifest["font"] = "preview/" + manifest["font"]
    json_write(project / "render-manifest.json", manifest)
    if engine == "hyperframes":
        from app.daily.hyperframes import invoke_renderer
    else:
        from app.daily.remotion import invoke_renderer

    invoke_renderer(project, check=True, template_project=project)
    store_version(base, previous_theme, previous_revision, engine)
    store_version(project, metadata["props"]["theme"], metadata["revision"], engine)
    json_write(root(engine) / "active.json", {"engine": engine, "revision": metadata["revision"]})
    return {**document(engine), "preview": metadata}


def restore(revision: str, expected_revision: str, engine: Engine = "remotion") -> dict:
    _, _, active_revision = selection(engine)
    if active_revision != expected_revision:
        raise FileExistsError("Template changed")
    if not re.fullmatch(r"[a-f0-9]{64}", revision) or not (root(engine) / "versions" / revision / "version.json").is_file():
        raise FileNotFoundError("Template version not found")
    version = root(engine) / "versions" / revision
    metadata = json.loads((version / "version.json").read_text(encoding="utf-8"))
    if metadata.get("engine", "remotion") != engine:
        raise ValueError("Template engine does not match version")
    theme = metadata["theme"]
    Theme.model_validate(theme)
    if fingerprint(sources(version, engine), theme, engine) != revision:
        raise ValueError("Template version contents changed")
    json_write(root(engine) / "active.json", {"engine": engine, "revision": revision})
    return document(engine)
