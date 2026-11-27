"""模板草稿、编译与不可变版本；不允许网页写任意工程文件。

网页只能提交 `descriptor()` 声明为可编辑的文件（Remotion：`src/video.tsx`、
`src/demo.tsx`、`src/types.ts`；HyperFrames：`src/template.html`、`src/demo.html`），
其余源码始终取自受信任工程，避免草稿替换预览桥接协议。

版本位于日报目录同级的 `video-template/`（HyperFrames 隔离在
`video-template/hyperframes/`）：`active.json` 指向当前 revision，
`versions/<sha256>/` 存放不可变源码，`previews/<id>/` 是可清理的临时预览。revision
是源码与主题的 SHA-256，内容一变旧的 `expected_revision` 就失效并抛
`FileExistsError`，防止覆盖别人刚保存的版本。

外部命令：node 执行 `video-renderer/scripts/build-editor.mjs` 完成类型检查与打包，
保存前还会用所选引擎真实渲染一帧。校验失败时 `active.json` 保持不变。
"""
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
# 网页唯一允许改写的文件；root.tsx 只读，避免 Composition 注册被草稿替换。
EDITABLE = ("src/video.tsx", "src/demo.tsx", "src/types.ts")
SOURCE_FILES = (*EDITABLE, "src/root.tsx", "src/index.ts", "src/editor-preview.tsx", "src/template-defaults.json")
Engine = Literal["remotion", "hyperframes"]
HYPERFRAMES_RENDERER = RENDERER.parent / "hyperframes-renderer"


def engine_name(engine: Engine | None = None) -> Engine:
    """解析并校验引擎标识。

    未显式传入时按 `DAILY_VIDEO_RENDERER` 推导：只有等于 hyperframes 才视为
    HyperFrames，其余（含 legacy）都按 Remotion 处理，保证旧配置行为不变。

    Raises:
        ValueError: 取值不属于 `remotion` 与 `hyperframes`。
    """
    value = engine or ("hyperframes" if settings.daily_video_renderer == "hyperframes" else "remotion")
    if value not in {"remotion", "hyperframes"}:
        raise ValueError("Unsupported template engine")
    return value


def descriptor(engine: Engine | None = None) -> dict:
    """返回某个引擎的模板工程描述。

    Returns:
        含 `engine`、展示名 `label`、可编辑文件 `editable`、全部源码文件与渲染器
        目录的字典。HyperFrames 只允许改两个 HTML，Remotion 只允许改三个
        TS/TSX 文件，其余源码由受信任工程提供。
    """
    value = engine_name(engine)
    editable = ("src/template.html", "src/demo.html") if value == "hyperframes" else EDITABLE
    return {"engine": value, "label": "HyperFrames" if value == "hyperframes" else "Remotion",
            "editable": editable, "sources": (*editable, "src/template-defaults.json")
            if value == "hyperframes" else SOURCE_FILES,
            "renderer": HYPERFRAMES_RENDERER if value == "hyperframes" else RENDERER}


class Theme(BaseModel):
    """模板主题参数：配色、字号、安全区与动效强度。

    全部字段都是 `strict=True` 加 `extra="forbid"`：网页不能塞额外键，数字也不能
    用字符串冒充。这里的取值范围就是渲染器的安全边界，超出直接拒绝。
    """
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
    """网页提交的模板草稿：引擎、期望 revision、源码与主题。

    `engine` 默认 `remotion`：老客户端不带该字段时沿用原引擎，绝不按当前运行配置
    隐式写入另一个引擎。
    """
    model_config = ConfigDict(extra="forbid")
    # 老客户端未带引擎时固定使用 Remotion，不随运行配置隐式写入另一引擎。
    engine: Engine = "remotion"
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: dict[str, str]
    theme: Theme

    @model_validator(mode="after")
    def allowed_sources(self):
        """拒绝非本引擎可编辑的文件、空文件或超过 128 KiB 的源码。"""
        if set(self.sources) != set(descriptor(self.engine)["editable"]):
            raise ValueError("Only the engine's editable template files are accepted")
        if any(not text.strip() or len(text.encode("utf-8")) > 128 * 1024 for text in self.sources.values()):
            raise ValueError("Template files must contain 1..128 KiB of source")
        return self


class CompilationError(Exception):
    """模板未通过类型检查或打包时抛出，携带渲染器返回的逐条诊断。"""
    def __init__(self, diagnostics: list[dict]):
        self.diagnostics = diagnostics
        super().__init__("Template did not pass validation")


def root(engine: Engine | None = None) -> Path:
    """返回模板版本根目录（日报目录同级的 `video-template/`）并确保存在。

    HyperFrames 的版本隔离在 `video-template/hyperframes/`，与 Remotion 的
    `active.json`、`versions/` 互不覆盖。
    """
    directory = store.root().parent / "video-template"
    # 保留既有 active.json/versions 路径；新引擎的版本始终隔离。
    if engine_name(engine) == "hyperframes":
        directory /= "hyperframes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def json_write(path: Path, value: dict) -> None:
    """原子写入 JSON（临时文件加 `replace`），避免读到半个文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def sources(project: Path, engine: Engine = "remotion") -> dict[str, str]:
    """读取某个工程的全部源码文件，键为相对路径。"""
    return {name: (project / name).read_text(encoding="utf-8") for name in descriptor(engine)["sources"]}


def fingerprint(files: dict[str, str], theme: dict, engine: Engine = "remotion") -> str:
    """计算“源码加主题”的 SHA-256，作为不可变版本号。

    Remotion 保持原算法（摘要不含 engine 字段）以兼容现存版本；其他引擎把 engine
    计入摘要，避免两个引擎的同名版本互相覆盖。

    Returns:
        64 位小写十六进制字符串。
    """
    # Remotion 保留旧摘要算法，以兼容现存不可变版本。
    content = {"sources": files, "theme": theme}
    if engine != "remotion":
        content["engine"] = engine
    value = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def selection(engine: Engine | None = None) -> tuple[Path, dict, str]:
    """返回当前生效的模板工程、主题与 revision。

    没有 `active.json` 时退回渲染器自带的默认模板与 `src/template-defaults.json`。
    已激活时逐项校验：引擎一致、revision 格式合法、版本元数据引擎一致、主题通过
    `Theme` 校验、源码重算的摘要等于 revision。任何一项不符都抛 `ValueError`，
    宁可让保存失败也不接受被改动的版本。

    Returns:
        `(工程目录, 主题字典, revision)`。
    """
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
    """组装模板编辑器需要的完整文档。

    Returns:
        当前 revision、主题、按 Pydantic schema 生成的字段控件描述、默认主题、
        可见源码（标注是否可编辑）与最近 30 个版本。`current_engine` 反映运行配置，
        可能与正在编辑的 `engine` 不同。
    """
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
    """把源码字典写到目标工程的对应相对路径，必要时创建父目录。"""
    for name, text in files.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def preview_props(project: Path) -> dict:
    """为新预览工程准备渲染属性：复用最近一次真实清单并复制它引用的媒体。

    只复制清单引用到的音视频与字体，且必须落在原任务目录内、后缀在白名单里，
    不托管整个日报目录；找不到清单时退回一段内置开发示例，保证编辑器永远可预览。

    Raises:
        ValueError: 清单引用的媒体跑出原目录或格式不受支持。
    """
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
    """把草稿编译成一次性预览工程，返回工程路径与元数据。

    顺序：清理旧预览缓存（只动本模块 `previews/` 下 32 位十六进制目录，保留最近
    11 个）、校验 `expected_revision`、合并草稿源码、用受信任工程覆盖预览桥接
    代码、node 打包，最后读取 `diagnostics.json`。

    Args:
        body: 已通过 `Draft` 校验的草稿。

    Returns:
        `(预览工程目录, {"engine", "id", "revision", "created_at", "props"})`；
        revision 是源码加新主题的指纹。

    Raises:
        FileExistsError: 期间有人保存了别的版本。
        RuntimeError: 未配置 node 或打包失败。
        CompilationError: 类型检查或打包未通过，携带逐条诊断。
    """
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
    """把某个工程固化为不可变版本；同一 revision 已存在时保持原样（幂等）。"""
    target = root(engine) / "versions" / revision
    if not (target / "version.json").is_file():
        copy_project(target, sources(project, engine))
        json_write(target / "version.json", {"engine": engine, "created_at": now(), "theme": theme})


def save(body: Draft) -> dict:
    """编译、真实渲染一帧校验并原子切换 active 版本。

    保存前会用所选引擎真正渲染一帧（`check=True`），不调用配音与发布；校验通过才
    把旧版本与新版本写入 `versions/` 并改写 `active.json`。已有成片与审核不受影响，
    新版本只作用于之后的生成。

    Raises:
        FileExistsError: `expected_revision` 已失效。
        CompilationError / RuntimeError: 编译或渲染校验失败，`active.json` 不变。
    """
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
    """把某个历史版本重新设为 active，同样校验 revision 与内容指纹。

    Args:
        revision: 目标版本的 revision。
        expected_revision: 调用方看到的当前 revision，用于发现并发保存。
        engine: 版本所属引擎。

    Returns:
        切换后的模板文档，含完整源码与版本列表。

    Raises:
        FileNotFoundError: 目标版本不存在。
        FileExistsError: 当前 revision 已变化。
        ValueError: 引擎不一致或版本内容被改动。
    """
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
