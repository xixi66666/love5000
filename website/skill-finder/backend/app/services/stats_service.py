from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionRun, Repository, TrendingEntry


class StatsService:
    async def get_stats(self, session: AsyncSession) -> dict:
        total = await session.scalar(
            select(func.count(Repository.id)).where(Repository.available.is_(True))
        )

        positive_growth = await session.scalar(
            select(func.count(TrendingEntry.id)).where(
                TrendingEntry.period == "daily",
                TrendingEntry.stars_gained > 0,
            )
        )

        success_row = await session.execute(
            select(CollectionRun)
            .where(CollectionRun.status.in_(("SUCCESS", "PARTIAL")))
            .order_by(CollectionRun.finished_at.desc())
            .limit(1)
        )
        success = success_row.scalar_one_or_none()

        latest_run_row = await session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        latest_run = latest_run_row.scalar_one_or_none()

        return {
            "total_repositories": total,
            "positive_growth_today": positive_growth,
            "last_successful_collection_at": _iso(success.finished_at if success else None),
            "last_run_status": latest_run.status if latest_run else None,
            "last_run_id": latest_run.id if latest_run else None,
            "last_run_error": _collection_error(latest_run),
            "last_run_warning": _collection_warning(latest_run),
        }

    async def get_languages(self, session: AsyncSession) -> list[dict]:
        rows = await session.execute(
            select(Repository.language, func.count(Repository.id).label("count"))
            .where(
                Repository.available.is_(True),
                Repository.language.isnot(None),
            )
            .group_by(Repository.language)
            .order_by(func.count(Repository.id).desc(), Repository.language.asc())
        )
        return [{"language": language, "count": count} for language, count in rows.all()]


def _collection_warning(run: CollectionRun | None) -> str | None:
    if run is None or run.status != "PARTIAL":
        return None
    summary = run.error_summary or ""
    if "INTRO_AUTH_FAILED" in summary:
        return "榜单已更新，但简介服务认证失败，部分中文介绍暂不可用。"
    if "INTRO_GENERATION_FAILED" in summary:
        return "榜单已更新，但部分中文介绍生成失败，可先查看项目原始描述。"
    return "榜单已更新，部分来源或项目未完成采集。"


def _collection_error(run: CollectionRun | None) -> str | None:
    # 只返回固定的用户提示，不把异常中的连接串、凭据或内部路径暴露给浏览器。
    if run is None or run.status != "FAILED":
        return None
    summary = (run.error_summary or "").lower()
    if "timeout" in summary or "timed out" in summary:
        return "连接 GitHub 超时，请检查网络或代理后重试。"
    if "githubautherror" in summary:
        return "GitHub 认证失败，请检查访问令牌后重试。"
    if "githubratelimiterror" in summary:
        return "GitHub 请求额度已用尽，请稍后重试。"
    if "trendingscrapeerror" in summary:
        return "无法获取 GitHub 榜单，请检查网络或代理后重试。"
    return "采集执行失败，请检查服务日志后重试。"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
