"""每日日报主流程：选题 → 写稿 → 画面 → 母带 → 待审核。

`generate` 全程持有日报全局锁并负责失败落盘；`compose` 生成片头、项目与片尾分镜；
`build` 写 `script.txt`、`report.md` 后调用 `media.render` 产出成片。已经进入
`pending_review` 及之后状态的报告是不可变的，cron 重试不会覆盖人工批准的结果。

数据来自数据库（`RepositoryStore.daily_report_candidates`），不直接抓取网络；外部
命令（node / ffmpeg / ffprobe）经渲染与母带模块间接调用。口播只截完整句并优先保留
限制条件；当天 AI 项目不足 10 个时如实标注，不补旧数据、不虚构项目。
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.daily import store
from app.daily.media import render
from app.daily.progress import current, tracking
from app.db.session import async_session_factory
from app.repositories.repositories import RepositoryStore

logger = logging.getLogger(__name__)

NARRATION_LIMIT = 360
SOURCE_NOTICE = "完整说明与使用限制，请查看日报中的项目来源。"
# 口播预算裁剪时用来识别不能丢的限制条件：风险、许可、硬件、付费、实验状态等。
CAUTION = re.compile(
    r"注意|限制|风险|不(?:支持|适合|可|能|建议)|尚未|暂不|仅(?:供|支持|适用|限)|"
    r"需要|仍需|必须|依赖|付费|收费|商用|许可|协议|实验|测试阶段|内测|显存|内存|GPU|CPU",
    re.IGNORECASE,
)


def now() -> str:
    """返回业务时区下的 ISO 时间戳。

    时区来自 `settings.business_timezone`（默认 Asia/Shanghai），报告里所有时间都
    用它书写，与服务器本地时区无关。
    """
    return datetime.now(ZoneInfo(settings.business_timezone)).isoformat()


def summarize(introduction: str | None, description: str | None) -> str:
    """从数据库字段里取一段可展示的项目简介。

    `introduction` 既可能是 JSON（`{"introduction": ...}`）也可能是纯文本，两种
    都要兼容；都为空时给出一句明确的缺省说明，而不是空字符串。
    """
    if introduction:
        try:
            payload = json.loads(introduction)
            text = payload.get("introduction", "") if isinstance(payload, dict) else ""
        except (ValueError, TypeError):
            text = introduction
        if isinstance(text, str) and text.strip():
            # 日报保留完整事实；口播在完整句界单独控制预算，避免截掉名称或尾部限制。
            return text.strip()
    return (description or "项目尚未提供简介，请通过仓库链接查看说明。").strip()


def spoken_text(text: str) -> str:
    """仅清理展示语法，不改写项目用途、名称、数值和使用条件。

    去掉链接与引用式链接定义、代码围栏、HTML 展示标签、标题与列表前缀、强调标记；
    删除线代表撤回，整段丢弃而不是朗读。只识别明确的展示标签，保住 `RAM < 16 GB`、
    `> 0.5` 这类比较条件和占位符。

    Returns:
        以中文句号收尾的单段文本。
    """
    value = html.unescape(text)
    value = re.sub(r"(?m)^\s*\[[^]\n]+\]:\s*https?://\S+.*$", "", value)
    value = re.sub(r"!?\[([^]\n]*)\]\((?:[^()\n]|\([^()\n]*\))*\)", r"\1", value)
    value = re.sub(r"\[([^]\n]+)\]\[[^]\n]*\]", r"\1", value)
    value = re.sub(r"(?m)^[ \t]*```[^\n]*$", "", value)
    # 删除线表示撤回，不能把标记去掉后重新当作有效事实朗读。
    value = re.sub(r"~~.*?~~", "", value, flags=re.DOTALL)
    value = re.sub(r"<(del|s|strike)\b[^>]*>.*?</\1\s*>", "", value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<(?:https?://|www\.)[^<>\s]+>", "", value, flags=re.IGNORECASE)
    value = re.sub(r"</?(?:p|br|div|li|h[1-6])\b[^>]*>", " ", value, flags=re.IGNORECASE)
    # 只识别明确的展示标签；保留 RAM < 16 GB、分数 > 0.5 等比较条件和参数占位符。
    value = re.sub(r"</?(?:a|abbr|b|strong|em|i|span|code|kbd|samp|small|sub|sup|mark|u|"
                   r"ins|wbr|img|pre|blockquote|ul|ol|table|tr|td|th|thead|tbody)\b[^>]*>", "",
                   value, flags=re.IGNORECASE)
    value = re.sub(
        r"(?:https?://|www\.)[^\s<>，。！？；、]+",
        lambda match: re.search(r"[.,;:!?]+$", match[0])[0]
        if re.search(r"[.,;:!?]+$", match[0]) else "",
        value,
    )
    value = re.sub(r"(?m)^[ \t]{0,3}(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)", "", value)
    value = re.sub(r"(`{1,3}|\*\*)(.*?)\1", r"\2", value, flags=re.DOTALL)
    value = re.sub(r"(?<![A-Za-z0-9_])\*([^*\n]+)\*(?![A-Za-z0-9_])", r"\1", value)
    value = re.sub(r"[；;]", "。", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"([。！？!?])。+", r"\1", value).strip(" ，、；;")
    return value + ("。" if value and value[-1] not in "。.!！?？" else "")


def narration_excerpt(text: str, budget: int) -> str:
    """长简介只选完整句，优先保留明确限制；放不下时提示用户查看完整来源。

    含 `CAUTION` 关键词的句子（限制、风险、许可、硬件要求等）必定入选，其余句子
    按原顺序填满预算；限制本身放不下时只返回 `SOURCE_NOTICE`，绝不截断限制条件
    或凭猜测压缩原文。

    Args:
        text: 已清理过的简介文本。
        budget: 口播可用字数，包含来源提示本身。

    Returns:
        可直接朗读的文本；完整原文仍保留在日报的 `summary` 字段里。
    """
    if len(text) <= budget:
        return text
    sentences = [piece.strip() for piece in re.findall(r"[^。！？!?]+[。！？!?]*", text)
                 if piece.strip()]
    available = max(0, budget - len(SOURCE_NOTICE))
    required = {index for index, piece in enumerate(sentences) if CAUTION.search(piece)}
    used = sum(len(sentences[index]) for index in required)
    if used > available:
        # 不截断限制条件或凭猜测压缩原文；完整原文仍保留在日报 summary。
        return SOURCE_NOTICE
    selected = set(required)
    for index, piece in enumerate(sentences):
        if index not in selected and used + len(piece) <= available:
            selected.add(index)
            used += len(piece)
    return "".join(sentences[index] for index in sorted(selected)) + SOURCE_NOTICE


def project_narration(item: dict) -> str:
    """拼出单个项目的口播句：排名、名称和受预算约束的简介。

    简介已以项目名开头时不再重复名称（按词边界判断，避免把 `ReactFlow` 当成
    `React` 的前缀）；名称与 Star 仍完整出现在画面和日报里。

    Args:
        item: `candidates` 产出的项目字典，需含 `rank`、`full_name`、`summary`。

    Returns:
        以句号结尾的口播文本。
    """
    name = item["full_name"].rsplit("/", 1)[-1]
    text = spoken_text(item["summary"])
    # 原简介已以项目名称开头时不连续重复名称；仓库全名和 Star 仍展示在画面及日报。
    starts_with_name = text.casefold().startswith(name.casefold()) and (
        len(text) == len(name) or not re.match(r"[A-Za-z0-9_.-]", text[len(name)])
    )
    prefix = f"第 {item['rank']} 名。" if starts_with_name else f"第 {item['rank']} 名，{name}。"
    return prefix + narration_excerpt(text or SOURCE_NOTICE, NARRATION_LIMIT - len(prefix))


async def candidates(day: str) -> list[dict]:
    """读取当天截止时刻之前入库的候选项目，并按榜单顺序编号。

    Args:
        day: `YYYY-MM-DD`，其 00:00（业务时区）换算成 UTC 作为截止时间。

    Returns:
        按今日新增 Star 排序的项目列表，每项含 `rank`、`full_name`、`url`、
        `description`、`summary`、`daily_stars`、`total_stars`、`snapshot_at`；
        数据库没有数据时返回空列表，由调用方决定失败文案。

    Notes:
        复用全局 async session 工厂，必须与采集步骤在同一事件循环里调用。
    """
    timezone = ZoneInfo(settings.business_timezone)
    cutoff = datetime.combine(datetime.fromisoformat(day).date(), time.min, timezone)
    cutoff = cutoff.astimezone(UTC).replace(tzinfo=None)
    async with async_session_factory() as session:
        rows = await RepositoryStore(session).daily_report_candidates(cutoff)
        return [
            {
                "rank": i,
                "full_name": repo.full_name,
                "url": repo.html_url,
                "description": repo.description,
                "summary": summarize(repo.introduction, repo.description),
                "daily_stars": entry.stars_gained,
                "total_stars": repo.stars_count,
                "snapshot_at": entry.fetched_at.replace(tzinfo=UTC).isoformat(),
            }
            for i, (repo, entry) in enumerate(rows, 1)
        ]


def compose(items: list[dict], day: str) -> tuple[str, list[dict]]:
    """把项目列表编排成分镜：片头、逆序项目、片尾。

    口播从最后一名讲到第一名，画面仍标注真实 rank；片头和片尾是固定文案，不含
    任何未观测到的数据。

    Returns:
        `(标题, 分镜列表)`；标题形如 `MM月DD日 GitHub AI Top N`。
    """
    count = len(items)
    title = f"{day[5:7]}月{day[8:]}日 GitHub AI Top {count}"
    scenes = [{
        "label": f"TOP {count}", "heading": "今天的 AI 工具，先看用途。",
        "summary": "按 GitHub Trending 日榜今日新增 Star 排序，从后向前逐个讲用途。",
        "narration": f"今天这 {count} 个 AI 项目，哪些能帮你解决实际问题？从后往前看。",
    }]
    for item in reversed(items):
        scenes.append({
            "label": f"#{item['rank']:02}", "heading": item["full_name"],
            "growth": item["daily_stars"], "summary": item["summary"],
            "narration": project_narration(item),
        })
    scenes.append({
        "label": "NEXT", "heading": "收藏榜单，选一个真正用起来。",
        "summary": "榜单反映当日关注度；完整来源和项目链接见日报。",
        "narration": "完整项目链接和数据快照已保存在日报。热度不等于质量，"
        "挑一个能解决实际问题的项目，动手试试。我们明早八点见。",
    })
    return title, scenes


def generate(*, collect: bool = False) -> dict:
    """生成当天日报并停在待审核状态。

    全程持有日报全局锁。已经进入审核流程（`pending_review` 及之后）的报告不可变，
    直接原样返回，避免 cron 重试覆盖人工批准。失败时把报告写成 `failed` 并记录异常
    类型，不写入任何伪造的产物。

    Args:
        collect: 是否在生成前真正执行一次采集；默认复用数据库已有榜单。

    Returns:
        报告字典；成功时 `status` 为 `pending_review`。

    Raises:
        透传 `build` 的异常，便于 CLI 与调度器记录失败。
    """
    with store.lock():
        day = now()[:10]
        try:
            existing = store.load(day)
        except FileNotFoundError:
            existing = None
        # 已进入审核流程的报告不可变；cron 重试不能覆盖人工批准。
        if existing and existing.get("status") in {
            "pending_review", "approved", "rejected", "publishing", "published", "publish_unknown",
        }:
            return existing
        report = {
            "date": day, "status": "generating", "created_at": now(),
            "scope": "AI / Agent / Skill / MCP / Plugin", "source": "GitHub Trending daily",
            "qq_status": "not_configured" if not settings.daily_qq_target else "pending",
            "publisher_status": "awaiting_login", "items": [],
        }
        store.save(report)
        try:
            with tracking(day) as progress:
                return build(report, day, collect, progress)
        except Exception as exc:
            logger.exception("Daily report generation failed")
            report.update(status="failed", error=type(exc).__name__, failed_at=now())
            store.save(report)
            raise


def build(report: dict, day: str, collect: bool, progress) -> dict:
    """执行选题之后的全部步骤：写稿、落盘、渲染、标记待审核。

    依次写 `script.txt` 与 `report.md`，再调用 `media.render` 产出成片；渲染结果
    只从 `render-result.json` 读取（那是统一验收后的正式结果），并记录成片的
    SHA-256 与审核摘要，供发布前比对。

    Args:
        report: 已保存的骨架报告，本函数原地更新并多次持久化。
        day: `YYYY-MM-DD`。
        collect: 透传给 `prepare`。
        progress: `progress.Tracker` 实例。

    Returns:
        完成后的报告字典，`status="pending_review"`。

    Raises:
        RuntimeError: 当天没有有效榜单项。
    """
    items = asyncio.run(prepare(day, collect=collect))
    if not items:
        raise RuntimeError("No fresh daily AI ranking; collect data and retry")
    progress.begin("script", "正在编排口播、来源和发布文案。")
    title, scenes = compose(items, day)
    script = "\n\n".join(scene["narration"] for scene in scenes)
    report.update(
        title=title, items=items, script=script,
        caption=f"{title}。按官方日榜新增 Star 排序，逐个讲用途。"
        "#GitHub #开源项目 #人工智能 #AI工具",
        item_count=len(items),
        completeness="top10" if len(items) == 10 else "insufficient_ai_projects",
    )
    store.save(report)
    directory = store.report_dir(day)
    (directory / "script.txt").write_text(script, encoding="utf-8")
    markdown = f"# {title}\n\n生成时间：{now()}\n\n"
    markdown += "范围：AI 项目；来源：GitHub Trending daily；按今日新增 Star 排序。\n\n"
    if len(items) < 10:
        markdown += f"当日匹配范围仅有 {len(items)} 个项目，未补入旧数据或虚构项目。\n\n"
    for item in items:
        markdown += (
            f"## {item['rank']}. [{item['full_name']}]({item['url']})\n\n"
            f"今日 +{item['daily_stars']:,} Star / 总计 {item['total_stars']:,} Star\n\n"
            f"{item['summary']}\n\n快照时间（UTC）：{item['snapshot_at']}\n\n"
        )
    (directory / "report.md").write_text(markdown, encoding="utf-8")
    progress.finish("script", f"已生成 {len(scenes)} 段口播与 {len(items)} 个项目来源。")
    progress.begin("assets", "正在检查渲染环境并准备项目素材。")
    report["duration_seconds"] = render(scenes, day, directory)
    if (directory / "render-result.json").is_file():
        report["render"] = json.loads((directory / "render-result.json").read_text(encoding="utf-8"))
        report["render"]["tts_provider"] = settings.daily_tts_provider
    report.update(
        status="pending_review", completed_at=now(),
        video_sha256=store.digest(directory / "video.mp4"),
    )
    report["review_digest"] = store.approval_digest(report)
    store.save(report)
    progress.ready()
    return report


async def prepare(day: str, *, collect: bool) -> list[dict]:
    """可选采集加选题，返回带真实排名的项目列表。

    Args:
        day: `YYYY-MM-DD`。
        collect: 为真时调用调度器的采集流程，否则复用数据库已有榜单。

    Returns:
        项目列表；不足 10 个时按实际数量返回，不补旧数据。

    Raises:
        RuntimeError: 采集之后仍没有符合范围的数据。
    """
    # 采集与选题必须共用同一事件循环上的 SQLAlchemy 异步连接池。
    progress = current()
    if collect:
        if progress:
            progress.begin("collection", "正在采集 GitHub Trending 并补全仓库信息。")
        from app.core.scheduler import _scheduled_collection

        await _scheduled_collection()
        if progress:
            progress.finish("collection", "采集调用已结束，接下来核对当天有效数据。")
    elif progress:
        progress.set("collection", "skipped", "复用数据库中已有的当天榜单。")
    if progress:
        progress.begin("selection", "正在筛选当天 AI 项目并按新增 Star 排序。")
    items = await candidates(day)
    if not items:
        raise RuntimeError("No fresh daily AI ranking; collect data and retry")
    if progress:
        progress.finish("selection", f"已选出 {len(items)} 个真实项目，不足十项时保留实际数量。")
    return items
