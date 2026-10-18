from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.daily import store
from app.daily.media import render
from app.db.session import async_session_factory
from app.repositories.repositories import RepositoryStore

logger = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(ZoneInfo(settings.business_timezone)).isoformat()


def summarize(introduction: str | None, description: str | None) -> str:
    if introduction:
        try:
            payload = json.loads(introduction)
            text = payload.get("introduction", "") if isinstance(payload, dict) else ""
        except (ValueError, TypeError):
            text = introduction
        if text:
            return text[:150].rstrip("，、；") + ("。" if text[-1] not in "。.!！" else "")
    return (description or "项目尚未提供简介，请通过仓库链接查看说明。")[:180]


async def candidates(day: str) -> list[dict]:
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
    count = len(items)
    title = f"{day[5:7]}月{day[8:]}日 GitHub AI Top {count}"
    scenes = [{
        "label": f"TOP {count}", "heading": "今天，哪些 AI 项目值得关注？",
        "summary": "按 GitHub Trending 日榜今日新增 Star 排序，从后向前逐个讲用途。",
        "narration": f"今天的 GitHub AI 项目热榜来了。选出日榜中增长最快的 {count} 个 AI 项目，"
        f"从第 {count} 名倒数到第一名，带你看它们能做什么。",
    }]
    for item in reversed(items):
        narration = (
            f"第 {item['rank']} 名，{item['full_name'].split('/')[-1]}。"
            f"今日新增 {item['daily_stars']} 颗星。{item['summary']}"
        )
        scenes.append({
            "label": f"#{item['rank']:02}", "heading": item["full_name"],
            "growth": item["daily_stars"], "summary": item["summary"], "narration": narration,
        })
    scenes.append({
        "label": "NEXT", "heading": "收藏榜单，选一个真正用起来。",
        "summary": "榜单反映当日关注度；完整来源和项目链接见日报。",
        "narration": "完整项目链接和数据快照已保存在日报。热度不等于质量，"
        "挑一个能解决实际问题的项目，动手试试。我们明早八点见。",
    })
    return title, scenes


def generate(*, collect: bool = False) -> dict:
    with store.lock():
        day = now()[:10]
        try:
            existing = store.load(day)
        except FileNotFoundError:
            existing = None
        # A report that has reached review is immutable; no cron retry can replace an approval.
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
            items = asyncio.run(prepare(day, collect=collect))
            if not items:
                raise RuntimeError("No fresh daily AI ranking; collect data and retry")
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
            report["duration_seconds"] = render(scenes, day, directory)
            report.update(
                status="pending_review", completed_at=now(),
                video_sha256=store.digest(directory / "video.mp4"),
            )
            report["review_digest"] = store.approval_digest(report)
            store.save(report)
            return report
        except Exception as exc:
            logger.exception("Daily report generation failed")
            report.update(status="failed", error=type(exc).__name__, failed_at=now())
            store.save(report)
            raise


async def prepare(day: str, *, collect: bool) -> list[dict]:
    # The global SQLAlchemy async pool must stay on the same event loop for both steps.
    if collect:
        from app.core.scheduler import _scheduled_collection

        await _scheduled_collection()
    return await candidates(day)
