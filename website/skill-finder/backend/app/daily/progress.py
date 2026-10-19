"""按真实执行节点保存进度；与审核报告分开写，避免覆盖批准摘要。"""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.daily import store

STEPS = [
    ("collection", "采集榜单", "采集 GitHub Trending 日榜并补全项目数据。"),
    ("selection", "筛选项目", "读取当天 AI 项目并核对真实排名和数量。"),
    ("script", "编排脚本", "生成短句口播、项目来源和发布文案。"),
    ("assets", "准备素材", "检查渲染环境，校验并固化项目演示素材。"),
    ("voice", "生成配音", "逐段合成配音，保留自然停顿与重点。"),
    ("captions", "对齐字幕", "根据实际音轨取得时间轴，并以原稿校正文字。"),
    ("render", "渲染成片", "合成动画、素材、音轨、字幕与封面。"),
    ("review", "人工审核", "预览当前视频，核对口播、来源与发布文案。"),
    ("publish", "抖音发布", "批准当前版本并登录账号后提交，未知结果不自动重发。"),
    ("notify", "消息送达", "可选 QQ 日报通知，成片就绪即可独立发送。"),
]
RECOVERY = {
    "collection": "检查采集网络和数据库连接后，重新运行今日流程。",
    "selection": "确认今天已有符合范围的 AI 日榜数据，再重新运行。",
    "script": "检查当天项目资料后重新运行；不使用旧项目补足数量。",
    "assets": "查看环境检查与缺失素材，为对应项目补充演示后重新运行。",
    "voice": "检查私有配音配置、供应商额度和网络，再重新运行。",
    "captions": "检查本地 Whisper 模型及音轨对齐；不要用估算时长替代。",
    "render": "查看 Node、浏览器、FFmpeg 和内存配置后重新运行。",
}
_current: ContextVar[Tracker | None] = ContextVar("daily_progress", default=None)


def now() -> str:
    return datetime.now(ZoneInfo(settings.business_timezone)).isoformat()


def blank(day: str) -> dict:
    return {"version": 1, "date": day, "attempt": uuid4().hex, "state": "idle", "current": None,
            "updated_at": now(), "events": [], "stages": [
                {"id": key, "label": label, "description": description, "status": "pending",
                 "detail": "", "done": 0, "total": 0}
                for key, label, description in STEPS
            ]}


def load(day: str) -> dict | None:
    try:
        return json.loads((store.report_dir(day) / "workflow.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Tracker:
    def __init__(self, day: str, *, reset: bool = False):
        self.day = day
        previous = None if reset else load(day)
        self.data = previous or blank(day)
        if not reset and previous is None:
            try:
                report = store.load(day)
            except FileNotFoundError:
                report = {}
            if report.get("status") in {"pending_review", "approved", "rejected", "publishing", "published", "publish_unknown"}:
                for stage in self.data["stages"][:7]:
                    stage.update(status="untracked", detail="历史任务未保存逐步记录。")

    def save(self) -> None:
        directory = store.report_dir(self.day)
        directory.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = now()
        # 写者持有日报全局锁（或 API 派发锁）；读取者只看完整快照。
        target = directory / "workflow.json"
        temporary = directory / (".workflow-" + uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)

    def stage(self, key: str) -> dict:
        return next(item for item in self.data["stages"] if item["id"] == key)

    def set(self, key: str, status: str, detail: str = "", **values) -> None:
        item = self.stage(key)
        changed = item["status"] != status or item["detail"] != detail
        item.update(status=status, detail=detail, **values)
        if status == "running":
            item.setdefault("started_at", now())
            self.data.update(state="running", current=key)
        elif status in {"completed", "skipped", "failed", "blocked", "uncertain"}:
            item["finished_at"] = now()
        if changed:
            self.data["events"].append({"at": now(), "stage": key, "status": status, "message": detail})
            self.data["events"] = self.data["events"][-100:]
        self.save()

    def begin(self, key: str, detail: str, *, total: int | None = None) -> None:
        self.set(key, "running", detail, **({"total": total} if total is not None else {}))

    def tick(self, key: str, detail: str) -> None:
        stage = self.stage(key)
        done = stage["done"] + 1
        self.set(key, "completed" if stage["total"] and done >= stage["total"] else "running",
                 detail, done=done)

    def finish(self, key: str, detail: str) -> None:
        self.set(key, "completed", detail)

    def ready(self) -> None:
        self.data.update(state="ready", current="review")
        self.set("review", "waiting", "成片已就绪，请校对视频、口播和发布文案。")
        if not (settings.daily_qq_target and settings.daily_openclaw_command):
            self.set("notify", "skipped", "QQ 接入口暂未配置。")

    def fail(self, error: BaseException) -> None:
        key = self.data.get("current") or "collection"
        self.data.update(state="failed", error=type(error).__name__)
        self.set(key, "failed", RECOVERY.get(key, "检查任务配置后重试。"), error=type(error).__name__)


def current() -> Tracker | None:
    return _current.get()


@contextmanager
def tracking(day: str):
    tracker = Tracker(day, reset=True)
    token = _current.set(tracker)
    try:
        yield tracker
    except Exception as error:
        tracker.fail(error)
        raise
    finally:
        _current.reset(token)
