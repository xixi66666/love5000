"""按真实执行节点保存进度；与审核报告分开写，避免覆盖批准摘要。

`workflow.json` 记录 10 个固定步骤的状态、计数、时间戳和最近 100 条事件，由
`Tracker` 在步骤真正开始/结束时写入，从不推断没有发生的步骤。`tracking` 是生成
流程唯一的进度上下文，异常时把当前步骤标记为失败并附上恢复建议。

读写都使用临时文件加 `replace` 原子替换，读方只会看到完整快照；工作流快照写成功
不代表报告可以发布，两者互相独立。
"""
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
    """返回业务时区的 ISO 时间戳，与 `workflow.json` 的时间字段保持一致。"""
    return datetime.now(ZoneInfo(settings.business_timezone)).isoformat()


def blank(day: str) -> dict:
    """创建一份全新的空白工作流快照。

    `attempt` 每次都是新的 UUID，用于区分同一天的重跑；10 个步骤初始为 `pending`，
    计数都为 0。
    """
    return {"version": 1, "date": day, "attempt": uuid4().hex, "state": "idle", "current": None,
            "updated_at": now(), "events": [], "stages": [
                {"id": key, "label": label, "description": description, "status": "pending",
                 "detail": "", "done": 0, "total": 0}
                for key, label, description in STEPS
            ]}


def load(day: str) -> dict | None:
    """读取已存在的 `workflow.json`。

    Returns:
        解析后的字典；文件不存在或内容损坏时返回 `None`，由调用方按“无记录”处理。
        这里不抛异常，避免历史任务缺文件时打断操作台。
    """
    try:
        return json.loads((store.report_dir(day) / "workflow.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Tracker:
    """把真实执行节点写入 `workflow.json` 的进度记录器。

    每次 `set` 都原子落盘，操作台随时能看到最新状态；进程被杀时最多丢掉一次未完成
    的写入。记录器只反映已经发生的动作，不预填后续步骤。
    """
    def __init__(self, day: str, *, reset: bool = False):
        """加载已有快照或新建一份。

        Args:
            day: `YYYY-MM-DD`。
            reset: 为真时丢弃旧记录重新开始（生成流程使用），否则续写。

        非 reset 且没有历史 workflow 时，若报告已进入审核之后的阶段，会把前 7 个
        步骤标为 `untracked`，明确表示当时没有记录，而不是补造进度。
        """
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
        """原子写入 `workflow.json` 并刷新 `updated_at`。

        先写同目录的隐藏临时文件再 `replace`；进程被杀死时最多丢掉一次未完成的写入，
        遗留的 `.workflow-*.tmp` 不会被任何读取方解析。
        """
        directory = store.report_dir(self.day)
        directory.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = now()
        # 写者持有日报全局锁（或 API 派发锁）；读取者只看完整快照。
        target = directory / "workflow.json"
        temporary = directory / (".workflow-" + uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)

    def stage(self, key: str) -> dict:
        """按 id 取出步骤字典，供就地读取或修改计数。"""
        return next(item for item in self.data["stages"] if item["id"] == key)

    def set(self, key: str, status: str, detail: str = "", **values) -> None:
        """更新单个步骤的状态与说明，必要时追加事件。

        状态为 `running` 时补齐 `started_at` 并把快照置为运行中；终态
        （completed / skipped / failed / blocked / uncertain）补齐 `finished_at`。
        只有状态或说明真正变化时才写事件，事件只保留最近 100 条。
        """
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
        """把步骤标记为运行中，可同时登记总工作量。"""
        self.set(key, "running", detail, **({"total": total} if total is not None else {}))

    def tick(self, key: str, detail: str) -> None:
        """推进一次计数；达到 `total` 时自动转为完成，否则保持运行中。"""
        stage = self.stage(key)
        done = stage["done"] + 1
        self.set(key, "completed" if stage["total"] and done >= stage["total"] else "running",
                 detail, done=done)

    def finish(self, key: str, detail: str) -> None:
        """把步骤标记为完成。"""
        self.set(key, "completed", detail)

    def ready(self) -> None:
        """成片就绪：切到等待人工审核，并在未配置 QQ 时直接跳过通知步骤。"""
        self.data.update(state="ready", current="review")
        self.set("review", "waiting", "成片已就绪，请校对视频、口播和发布文案。")
        if not (settings.daily_qq_target and settings.daily_openclaw_command):
            self.set("notify", "skipped", "QQ 接入口暂未配置。")

    def fail(self, error: BaseException) -> None:
        """把当前步骤标记为失败，并写入该步骤的恢复建议。

        Args:
            error: 触发失败的异常；只记录类型名，避免把私有细节写进可展示状态。
        """
        key = self.data.get("current") or "collection"
        self.data.update(state="failed", error=type(error).__name__)
        self.set(key, "failed", RECOVERY.get(key, "检查任务配置后重试。"), error=type(error).__name__)


def current() -> Tracker | None:
    """返回当前上下文绑定的进度记录器，没有则返回 `None`。"""
    return _current.get()


@contextmanager
def tracking(day: str):
    """生成流程的进度上下文：新建快照、绑定 ContextVar、失败时落盘。

    退出时总会恢复上一个 ContextVar 值，嵌套调用不会串台；异常会先由 `Tracker.fail`
    记录当前步骤，再原样抛出。
    """
    tracker = Tracker(day, reset=True)
    token = _current.set(tracker)
    try:
        yield tracker
    except Exception as error:
        tracker.fail(error)
        raise
    finally:
        _current.reset(token)
