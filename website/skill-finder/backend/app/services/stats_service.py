"""首页统计与语言分布。

只读服务：接收调用方传入的 ``AsyncSession``，不提交、不关闭。
除了聚合数字，这里还负责把 ``collection_runs.error_summary`` 翻译成固定的中文提示——
``/api/v1/stats`` 直接返回这些文案，因此**不能**把原始异常、SQL、连接串或
GitHub Token 拼进提示里（异常原文只留在服务端日志与数据库）。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionRun, Repository, TrendingEntry


class StatsService:
    """统计聚合服务（无状态，可在请求间复用）。

    所有方法都要求调用方传入会话；服务内部不发写语句，因此路由不需要为它准备事务。
    """

    async def get_stats(self, session: AsyncSession) -> dict:
        """汇总仪表盘统计。

        Args:
            session: 调用方打开的只读会话，本方法不提交也不关闭。

        Returns:
            ``StatsResponse`` 对应的字典：可见仓库总数、当日正增长条目数、最近一次成功
            采集时间，以及最新任务的 ``last_run_status`` / ``last_run_id`` /
            ``last_run_error`` / ``last_run_warning``（后两者互斥，按状态决定）。
        """
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
        """按语言统计可见仓库数。

        Args:
            session: 调用方打开的只读会话。

        Returns:
            ``[{"language": ..., "count": ...}]``，按数量降序、同数按语言名升序；
            未标注语言的仓库被排除，避免出现空语言分组。
        """
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
    """把 ``PARTIAL`` 任务的关键字翻译成用户可读的警告。

    只认 ``collection_runs.error_summary`` 里约定的错误码（简介认证失败、简介生成失败），
    其他情况统一提示“部分来源未完成”，不猜测具体原因。

    Args:
        run: 最新任务行，可为 ``None``。

    Returns:
        警告文案；任务不是 ``PARTIAL`` 或没有任务时为 ``None``。
    """
    if run is None or run.status != "PARTIAL":
        return None
    summary = run.error_summary or ""
    if "INTRO_AUTH_FAILED" in summary:
        return "榜单已更新，但简介服务认证失败，部分中文介绍暂不可用。"
    if "INTRO_GENERATION_FAILED" in summary:
        return "榜单已更新，但部分中文介绍生成失败，可先查看项目原始描述。"
    return "榜单已更新，部分来源或项目未完成采集。"


def _collection_error(run: CollectionRun | None) -> str | None:
    """把 ``FAILED`` 任务的异常类型映射成固定提示。

    只按关键字（``timeout`` / ``GitHubAuthError`` / ``GitHubRateLimitError`` /
    ``TrendingScrapeError``）匹配，命不中则给通用文案；无论命中与否都不回显原文。

    Args:
        run: 最新任务行，可为 ``None``。

    Returns:
        提示文案；任务不是 ``FAILED`` 或没有任务时为 ``None``。
    """
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
    """把时间统一成带 ``Z`` 的 UTC ISO 字符串。

    MySQL DATETIME 取回来可能没有时区，这里按 UTC 补齐；前端只做展示，不需要再做
    时区换算。

    Args:
        value: 数据库时间或 ``None``。

    Returns:
        ``YYYY-MM-DDTHH:MM:SSZ`` 形式的字符串；输入为 ``None`` 时返回 ``None``。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
