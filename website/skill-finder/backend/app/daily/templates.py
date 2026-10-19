"""模板草稿、编译与不可变版本；不允许网页写任意工程文件。"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.daily import store
from app.daily.media import run
from app.daily.progress import now

RENDERER = Path(__file__).resolve().parents[3] / "video-renderer"
EDITABLE = ("src/video.tsx", "src/demo.tsx", "src/types.ts")
SOURCE_FILES = (*EDITABLE, "src/root.tsx", "src/index.ts", "src/editor-preview.tsx", "src/template-defaults.json")


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
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: dict[str, str]
    theme: Theme

    @field_validator("sources")
    @classmethod
    def allowed_sources(cls, value):
        if set(value) != set(EDITABLE):
            raise ValueError("Only the three editable template files are accepted")
        if any(not text.strip() or len(text.encode("utf-8")) > 128 * 1024 for text in value.values()):
            raise ValueError("Template files must contain 1..128 KiB of source")
        return value


class CompilationError(Exception):
    def __init__(self, diagnostics: list[dict]):
        self.diagnostics = diagnostics
        super().__init__("Template did not pass validation")


def root() -> Path:
    directory = store.root().parent / "video-template"
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def sources(project: Path) -> dict[str, str]:
    return {name: (project / name).read_text(encoding="utf-8") for name in SOURCE_FILES}


def fingerprint(files: dict[str, str], theme: dict) -> str:
    value = json.dumps({"sources": files, "theme": theme}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def selection() -> tuple[Path, dict, str]:
    try:
        active = json.loads((root() / "active.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        files = sources(RENDERER)
        theme = json.loads(files["src/template-defaults.json"])
        return RENDERER, theme, fingerprint(files, theme)
    revision = active["revision"]
    if not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise ValueError("Invalid active template revision")
    project = root() / "versions" / revision
    theme = json.loads((project / "version.json").read_text(encoding="utf-8"))["theme"]
    Theme.model_validate(theme)
    if fingerprint(sources(project), theme) != revision:
        raise ValueError("Template version contents changed")
    return project, theme, revision


def document() -> dict:
    project, theme, revision = selection()
    versions = []
    for filename in (root() / "versions").glob("*/version.json"):
        metadata = json.loads(filename.read_text(encoding="utf-8"))
        versions.append({"revision": filename.parent.name, "created_at": metadata["created_at"]})
    labels = {"accent": "强调色", "background": "画面背景", "foreground": "文字与面板", "brand": "栏目名称",
              "tagline": "栏目短句", "headlineSize": "标题字号", "captionSize": "字幕字号", "captionBottom": "字幕距底部",
              "safeRight": "右侧安全区", "mediaTop": "素材距顶部", "motion": "入场动效强度"}
    fields = []
    for key, schema in Theme.model_json_schema()["properties"].items():
        kind = "color" if key in {"accent", "background", "foreground"} else "text" if schema["type"] == "string" else "number"
        fields.append({"key": key, "label": labels[key], "kind": kind, "min": schema.get("minimum"),
                       "max": schema.get("maximum"), "step": 0.1 if key == "motion" else 1,
                       "maxLength": schema.get("maxLength")})
    return {"revision": revision, "theme": theme, "fields": fields,
            "defaults": json.loads((RENDERER / "src/template-defaults.json").read_text(encoding="utf-8")),
            "sources": [{"path": name, "code": (project / name).read_text(encoding="utf-8"),
                         "editable": name in EDITABLE} for name in (*EDITABLE, "src/root.tsx")],
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
    # 仅清理本模块生成的旧预览缓存；模板版本和日报目录不参与清理。
    cache = (root() / "previews").resolve()
    previous = sorted((path for path in cache.glob("*") if re.fullmatch(r"[a-f0-9]{32}", path.name)
                       and path.is_dir() and not path.is_symlink()), key=lambda path: path.stat().st_mtime, reverse=True)
    for obsolete in previous[11:]:
        target = obsolete.resolve()
        if target.parent == cache:
            shutil.rmtree(target)
    base, _, _ = selection()
    files = sources(base)
    files.update(body.sources)
    # 预览桥接代码始终来自可信工程，不允许草稿替换其消息协议。
    files["src/editor-preview.tsx"] = (RENDERER / "src/editor-preview.tsx").read_text(encoding="utf-8")
    project = root() / "previews" / uuid4().hex
    copy_project(project, files)
    node = shutil.which(settings.daily_node_command)
    if not node:
        raise RuntimeError("Node is not configured")
    run([node, str(RENDERER / "scripts/build-editor.mjs"), str(project)], cwd=RENDERER, timeout=90)
    diagnostics = json.loads((project / "diagnostics.json").read_text(encoding="utf-8"))
    if not diagnostics["ok"]:
        raise CompilationError(diagnostics["diagnostics"])
    props = preview_props(project)
    props["theme"] = body.theme.model_dump()
    revision = fingerprint(files, props["theme"])
    metadata = {"id": project.name, "revision": revision, "created_at": now(), "props": props}
    json_write(project / "preview.json", metadata)
    (project / "preview/index.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>模板预览</title>'
        '<style>html,body,#root{margin:0;width:100%;height:100%;background:#101618;color:#eee;'
        'font-family:system-ui}*{box-sizing:border-box}</style><div id="root"></div>'
        '<script src="app.js" defer></script></html>', encoding="utf-8",
    )
    return project, metadata


def store_version(project: Path, theme: dict, revision: str) -> None:
    target = root() / "versions" / revision
    if not (target / "version.json").is_file():
        copy_project(target, sources(project))
        json_write(target / "version.json", {"created_at": now(), "theme": theme})


def save(body: Draft) -> dict:
    base, previous_theme, previous_revision = selection()
    if previous_revision != body.expected_revision:
        raise FileExistsError("Template changed")
    project, metadata = compile_draft(body)
    # 保存前真正渲染一帧，捕获 React 运行错误；不调用配音或发布。
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
    from app.daily.remotion import invoke_renderer

    invoke_renderer(project, check=True, template_project=project)
    store_version(base, previous_theme, previous_revision)
    store_version(project, metadata["props"]["theme"], metadata["revision"])
    json_write(root() / "active.json", {"revision": metadata["revision"]})
    return {**document(), "preview": metadata}


def restore(revision: str, expected_revision: str) -> dict:
    _, _, active_revision = selection()
    if active_revision != expected_revision:
        raise FileExistsError("Template changed")
    if not re.fullmatch(r"[a-f0-9]{64}", revision) or not (root() / "versions" / revision / "version.json").is_file():
        raise FileNotFoundError("Template version not found")
    version = root() / "versions" / revision
    theme = json.loads((version / "version.json").read_text(encoding="utf-8"))["theme"]
    Theme.model_validate(theme)
    if fingerprint(sources(version), theme) != revision:
        raise ValueError("Template version contents changed")
    json_write(root() / "active.json", {"revision": revision})
    return document()
