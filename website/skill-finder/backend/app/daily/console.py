"""操作台只返回可展示的状态，不返回凭据、私有路径或上游异常正文。"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from filelock import Timeout

from app.core.config import settings
from app.daily import store
from app.daily.progress import blank, load, now
from app.daily.remotion import RENDERER_DIR


def asset_status(project: str) -> dict:
    root = Path(settings.daily_assets_dir).resolve()
    result = {"project": project, "status": "missing", "source": "", "filename": ""}
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", project):
        return {**result, "status": "invalid"}
    try:
        manifest = root / (project.replace("/", "--") + ".json")
        value = json.loads(manifest.read_text(encoding="utf-8"))
        original = (root / value["file"]).resolve()
        url = urlsplit(value["source"])
        if (not original.is_relative_to(root) or not original.is_file()
                or original.suffix.lower() not in {".mp4", ".png", ".jpg", ".jpeg"}
                or url.scheme != "https" or url.username or url.password):
            raise ValueError("Invalid asset")
        result.update(status="ready", source=value["source"], filename=original.name)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError):
        result["status"] = "invalid"
    return result


def runtime() -> list[dict]:
    remotion = settings.daily_video_renderer == "remotion"
    mimo = settings.daily_tts_provider == "mimo" and remotion
    return [
        {"id": "renderer", "label": "视频引擎", "value": settings.daily_video_renderer,
         "ready": not remotion or bool(shutil.which(settings.daily_node_command))
         and (RENDERER_DIR / "node_modules/remotion/package.json").is_file()},
        {"id": "ffmpeg", "label": "音视频工具", "value": "FFmpeg / ffprobe",
         "ready": bool(shutil.which(settings.daily_ffmpeg_command) and shutil.which(settings.daily_ffprobe_command))},
        {"id": "tts", "label": "配音服务", "value": settings.daily_tts_provider if remotion else "edge",
         "ready": not mimo or bool(settings.mimo_api_key.get_secret_value())},
        {"id": "captions", "label": "字幕对齐", "value": "Whisper / " + (
            settings.daily_whisper_model if re.fullmatch(r"[A-Za-z0-9_.-]+", settings.daily_whisper_model)
            else "本地模型")
         if mimo else "供应商时间戳" if remotion else "旧版估算字幕",
         "ready": not mimo or importlib.util.find_spec("faster_whisper") is not None},
        {"id": "publisher", "label": "抖音账号", "value": "已配置登录态" if Path(settings.douyin_storage_state).is_file()
         else "等待扫码登录", "ready": settings.douyin_publish_enabled
         and Path(settings.douyin_storage_state).is_file(), "optional": True},
        {"id": "notify", "label": "QQ 接入口", "value": "已配置" if settings.daily_qq_target
         and settings.daily_openclaw_command else "暂未配置", "ready": bool(settings.daily_qq_target
         and settings.daily_openclaw_command), "optional": True},
    ]


def samples() -> list[dict]:
    result = []
    for path in sorted((store.root().parent / "video-samples").glob("*/render-result.json"), reverse=True):
        if not re.fullmatch(r"\d{8}-\d{6}", path.parent.name) or not (path.parent / "video.mp4").is_file():
            continue
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            result.append({"id": path.parent.name, "duration_seconds": float(metadata["duration_seconds"]),
                           "width": int(metadata["width"]), "height": int(metadata["height"]), "fps": int(metadata["fps"])})
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if len(result) >= 10:
            break
    return result


def snapshot(day: str) -> dict:
    directory = store.report_dir(day)
    try:
        report = store.load(day)
    except FileNotFoundError:
        report = None
    workflow = load(day)
    recorded = workflow is not None
    workflow = workflow or blank(day)
    status = report.get("status", "idle") if report else workflow["state"]
    if workflow["state"] == "queued":
        status = "queued"
    stages = {step["id"]: step for step in workflow["stages"]}
    if report and not recorded:
        for key in ("collection", "selection", "script", "assets", "voice", "captions", "render"):
            stages[key].update(status="untracked", detail="历史任务未保存逐步记录，请以现有产物为准。")
    if status in {"pending_review", "approved", "rejected", "publishing", "published", "publish_unknown"}:
        stages["review"].update(
            status="waiting" if status == "pending_review" else "rejected" if status == "rejected" else "completed",
            detail="成片等待你审核。" if status == "pending_review" else "当前版本已退回，不会发布。"
            if status == "rejected" else "已记录当前视频和文案的批准。",
        )
        workflow["current"] = "review" if status in {"pending_review", "rejected"} else "publish"
        publishing = report.get("publisher_status")
        stages["publish"].update(
            status="completed" if status == "published" else "uncertain" if status == "publish_unknown"
            else "running" if status == "publishing" else "blocked" if status == "approved" else "pending",
            detail="发布成功。" if status == "published" else "结果未确认，请先到抖音作品管理核查，勿重复提交。"
            if status == "publish_unknown" else "正在上传并提交当前批准的视频。" if status == "publishing"
            else "请完成抖音登录后重试。" if publishing == "awaiting_login"
            else "请检查账号登录或创作者页面后重试。" if publishing == "login_or_ui_required"
            else "等待当前版本的人工批准。",
        )
        if status == "approved" and report.get("publisher_status") == "uploading":
            stages["publish"].update(status="running", detail="正在上传当前批准的视频。")
    interrupted = False
    if status in {"generating", "queued", "running"}:
        age = (datetime.fromisoformat(now()) - datetime.fromisoformat(workflow["updated_at"])).total_seconds()
        if age > 30:
            try:
                with store.lock():
                    interrupted = True
            except Timeout:
                pass
        if interrupted:
            status = "interrupted"
            key = workflow.get("current") or "collection"
            stages[key].update(status="interrupted", detail="任务已不再持有运行锁，可重新运行今日流程。")
    if report and report.get("qq_status") == "sent":
        stages["notify"].update(status="completed", detail="QQ 日报通知已送达。")
    elif not (settings.daily_qq_target and settings.daily_openclaw_command):
        stages["notify"].update(status="skipped", detail="QQ 接入口暂未配置，不影响视频流程。")
    frame_progress = None
    if stages["render"]["status"] == "running":
        try:
            value = json.loads((directory / "render-progress.json").read_text(encoding="utf-8"))
            frame_progress = {key: value[key] for key in
                              ("phase", "rendered_frames", "total_frames", "updated_at")}
        except (OSError, ValueError, KeyError):
            pass
    artifacts = []
    for name, label in [("video.mp4", "竖屏视频"), ("audio.m4a", "中文配音"), ("poster.png", "封面"),
                        ("subtitles.srt", "字幕"), ("script.txt", "口播脚本"), ("report.md", "文字日报")]:
        ready = (directory / name).is_file() and bool(report) and (
            name in {"script.txt", "report.md"} or report["status"] not in {"generating", "failed"})
        artifacts.append({"name": name, "label": label, "ready": ready})
    return {
        "date": day, "today": now()[:10], "timezone": settings.business_timezone, "status": status,
        "recorded": recorded, "workflow": workflow, "render_progress": frame_progress,
        "artifacts": artifacts, "assets": [asset_status(item["full_name"]) for item in (report or {}).get("items", [])],
        "runtime": runtime(), "samples": samples(), "template": {
            "composition": "SkillFinderDaily", "width": 1080, "height": 1920, "fps": 30,
            "directory": "website/skill-finder/video-renderer",
            "editor_url": "/daily-reports?panel=template",
            "api": "/api/v1/daily-reports/template",
            "files": [
                {"path": "src/video.tsx", "description": "主模板：布局、动效、字幕、项目素材和音轨"},
                {"path": "src/root.tsx", "description": "注册 Composition、分辨率、帧率和动态时长"},
                {"path": "src/demo.tsx", "description": "Remotion 本地能力演示"},
                {"path": "src/types.ts", "description": "场景、字幕和素材的数据协议"},
            ],
        },
    }
