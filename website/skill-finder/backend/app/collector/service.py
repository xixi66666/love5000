"""采集编排：抓榜单 → 过滤 → GitHub API 补全 → 落库 → 记录任务结果。

一次 :meth:`CollectionService.run` 的结果只有三种状态：

- ``SUCCESS``：三个周期都成功，且所有入选仓库都完成 API 补全；
- ``PARTIAL``：部分周期抓取失败、部分仓库补全失败，或中文简介缺失；
- ``FAILED``：鉴权/限流/三个周期全失败等无法产出榜单的错误。

降级原则：单个周期失败不影响其他周期；某周期的仓库补全后一个都不剩时**保留上一轮
榜单**（不写空表），避免网络抖动把页面刷成空白。

会话所有权：``session`` 由调用方（:func:`app.core.scheduler.run_collection`）用
``async_session_factory()`` 打开并关闭，本类只负责在每个阶段结束时 ``commit``，
从不 ``close``；异常路径交给上层上下文管理器回滚。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.classifier import classify_repository
from app.collector.github_client import (
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubRateLimitError,
    GitHubRepository,
    GitHubRequestError,
)
from app.collector.trending import (
    PERIODS,
    TrendingRepository,
    TrendingScrapeError,
    TrendingScraper,
    select_trending,
)
from app.core.config import settings
from app.db.models import CollectionRun, Repository
from app.repositories.collection_runs import CollectionRunStore
from app.repositories.repositories import RepositoryStore
from app.repositories.snapshots import SnapshotStore
from app.repositories.trending import TrendingEntryValue, TrendingStore

logger = logging.getLogger(__name__)

# 任务状态取值，写入 collection_runs.status；前端与 /api/v1/stats 依赖这三个字面量。
STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"


@dataclass
class CollectionResult:
    """一轮采集的计数与结果，最终映射到 ``collection_runs`` 一行。

    Attributes:
        run_id: 任务主键，接口与前端用它识别“这是不是本次刷新”。
        status: SUCCESS / PARTIAL / FAILED。
        period_count: 期望抓取的周期数（当前恒为 3）。
        discovered_count: 三个榜单页累计解析到的仓库条数。
        updated_count: 成功补全并写入 ``repositories`` 的仓库数。
        failed_count: 补全失败或被过滤掉的仓库数。
        rate_limit_remaining: 采集结束时 GitHub 剩余额度，可能未知。
        rate_limit_reset_at: 额度重置时间。
        error_summary: 失败/警告摘要，写入 ``error_summary``；前端据此生成固定提示。
        skipped_locked: 保留字段，用于标记因锁未获取而跳过的轮次。
    """

    run_id: int
    status: str
    period_count: int
    discovered_count: int
    updated_count: int
    failed_count: int
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None
    error_summary: str | None = None
    skipped_locked: bool = False


@dataclass
class CollectionService:
    """一次采集任务的编排者。

    依赖全部通过构造注入（爬虫、GitHub 客户端、四个仓储与一个会话），因此测试可以
    用替身覆盖任一环节而不联网；``discovered`` 累积原始榜单行，``_selected`` 保存
    每个周期过滤后的 Top N，二者都不落库，只用于本轮统计。

    会话由调用方打开与关闭，本类只在阶段边界 ``commit``。
    """

    scraper: TrendingScraper
    github_client: GitHubClient
    repository_store: RepositoryStore
    snapshot_store: SnapshotStore
    trending_store: TrendingStore
    run_store: CollectionRunStore
    session: AsyncSession
    business_timezone: str = "Asia/Shanghai"
    top_n: int = 10
    ai_keywords: str = ""
    trigger_type: str = "scheduled"
    discovered: list[TrendingRepository] = field(default_factory=list)

    def __post_init__(self) -> None:
        """初始化时区对象与每周期选择结果容器。

        时区在构造期解析一次：``ZoneInfo`` 对非法时区名会抛 ``KeyError``，
        让配置错误在任务开始前暴露，而不是等到写业务日期时才发现。
        """
        self._timezone = ZoneInfo(self.business_timezone)
        self._selected: dict[str, list[TrendingRepository]] = {}

    @property
    def _business_date(self) -> date:
        """按业务时区（默认 Asia/Shanghai）取今天，用于 Star 快照的日期键。

        不能用 UTC 时间：服务器凌晨跑采集时 UTC 还停在前一天，会与页面展示的
        “今天”错位。
        """
        return datetime.now(self._timezone).date()

    async def run(self) -> CollectionResult:
        """执行一轮完整采集并落库任务结果。

        流程：先创建 ``RUNNING`` 任务并立刻 commit（否则并发连接在采集期间只能读到
        上一轮结果），再逐周期抓取与补全，最后写终态。成功与部分成功都返回结果；
        鉴权失败、限流、全部周期抓取失败等抛出异常前会先把任务标记为 ``FAILED``，
        保证前端轮询能看到失败原因，而不是永远停在 RUNNING。

        Returns:
            本轮结果，含计数、限流信息与错误摘要。

        Raises:
            GitHubAuthError: Token 无效。
            GitHubRateLimitError: API 额度耗尽。
            TrendingScrapeError: 三个周期都没抓到榜单。
            Exception: 其他未预期异常同样先落 FAILED 再向上抛，交给任务框架记录。

        调用方负责关闭会话；本方法在每个阶段结束时 commit，不 close。
        """
        run = await self.run_store.create(self.trigger_type)
        # 先提交任务状态，避免采集期间其他连接始终只能读到上一次任务。
        await self.session.commit()
        result = CollectionResult(
            run_id=run.id,
            status=STATUS_SUCCESS,
            period_count=len(PERIODS),
            discovered_count=0,
            updated_count=0,
            failed_count=0,
        )
        try:
            await self._collect_periods(result)
            if len(self._selected) < len(PERIODS):
                result.status = STATUS_PARTIAL
            await self._persist_selected(result)
            if result.failed_count > 0:
                result.status = STATUS_PARTIAL
            await self._finish(run, result, status=result.status)
            return result
        except (GitHubAuthError, GitHubRateLimitError, TrendingScrapeError) as exc:
            result.status = STATUS_FAILED
            result.error_summary = _error_summary(exc)
            await self._finish(run, result, status=STATUS_FAILED)
            raise
        except Exception as exc:
            result.status = STATUS_FAILED
            result.error_summary = _error_summary(exc)
            await self._finish(run, result, status=STATUS_FAILED)
            raise

    async def _collect_periods(self, result: CollectionResult) -> None:
        """逐周期抓取并做 AI 过滤，单周期失败只记录不中断。

        三个周期全失败才抛 :class:`TrendingScrapeError`；部分失败时把失败原因写进
        ``result.error_summary``，由 :meth:`run` 判为 ``PARTIAL``。失败周期的旧榜单
        不会被覆盖，因为 ``_selected`` 里根本没有该周期的键。

        Args:
            result: 累积计数的结果对象，原地修改。

        Raises:
            TrendingScrapeError: 没有任何周期拿到数据。
        """
        failures: list[str] = []
        for period in PERIODS:
            try:
                repositories = await self.scraper.fetch(period)
            except TrendingScrapeError as exc:
                failures.append(f"{period}: {exc}")
                logger.warning("trending period %s failed: %s", period, exc)
                continue
            result.discovered_count += len(repositories)
            self.discovered.extend(repositories)
            self._selected[period] = select_trending(
                repositories, self.ai_keywords, self.top_n
            )
        if not self._selected:
            raise TrendingScrapeError(
                "all trending periods failed: " + "; ".join(failures)
            )
        if failures:
            result.error_summary = "; ".join(failures)

    async def _persist_selected(self, result: CollectionResult) -> None:
        """补全元信息、写仓库与快照、替换榜单、生成简介。

        以 ``full_name`` 去重（同一仓库可能同时出现在多个周期）。某个周期入选的仓库
        全部补全失败时跳过 ``replace_period``，保留上一轮榜单，并在日志里说明原因——
        这比写一张空表更符合“不伪造成功”的约束。

        本方法结束时 ``commit`` 一次，把仓库、快照、榜单与简介写入一起生效；
        简介缺失只把状态降为 ``PARTIAL``，不影响已经拿到的榜单数据。

        Args:
            result: 累积计数的结果对象，原地修改。
        """
        unique: dict[str, TrendingRepository] = {}
        for repositories in self._selected.values():
            for repository in repositories:
                unique.setdefault(repository.full_name, repository)

        stored: dict[str, Repository] = {}
        intro_pending: list[Repository] = []
        fetched_at = datetime.now(UTC)

        for full_name in unique:
            try:
                repo = await self.github_client.get_repository(full_name)
            except GitHubRequestError as exc:
                result.failed_count += 1
                logger.warning("failed to fetch %s: %s", full_name, exc)
                continue
            if repo is None or not self._eligible(repo):
                result.failed_count += 1
                continue

            classification = classify_repository(
                name=repo.name,
                description=repo.description or "",
                topics=repo.topics,
            )
            updated = await self.repository_store.upsert(repo, classification)
            await self.snapshot_store.upsert_daily(
                repository_id=updated.id,
                snapshot_date=self._business_date,
                stars_count=repo.stars_count,
            )
            stored[full_name] = updated
            result.updated_count += 1
            if settings.intro_enabled and updated.introduction is None:
                intro_pending.append(updated)

        for period, repositories in self._selected.items():
            entries = [
                TrendingEntryValue(
                    repository_id=stored[repository.full_name].id,
                    rank_position=rank,
                    stars_gained=repository.stars_gained,
                    stars_total=repository.stars_total or stored[repository.full_name].stars_count,
                )
                for rank, repository in enumerate(repositories, start=1)
                if repository.full_name in stored
            ]
            if repositories and not entries:
                logger.warning("preserving previous %s ranking after incomplete API enrichment", period)
                continue
            await self.trending_store.replace_period(period, entries, fetched_at)

        missing_intros, intro_error = await self._generate_introductions(intro_pending)
        if missing_intros:
            result.status = STATUS_PARTIAL
            warning = f"{intro_error}: missing={missing_intros}"
            result.error_summary = "; ".join(filter(None, (result.error_summary, warning)))
        await self._record_rate_limit(result)
        await self.session.commit()

    async def _record_rate_limit(self, result: CollectionResult) -> None:
        """把当前 GitHub 额度写进结果，便于事后判断是否被限流截断。

        这次查询自身失败会向上抛（``GitHubRequestError``），因为它发生在数据已写入
        之后，失败只会让任务落成 FAILED 或 PARTIAL，不会丢数据。

        Args:
            result: 结果对象，原地写入 ``rate_limit_*`` 两个字段。
        """
        rate_limit = await self.github_client.get_rate_limit()
        result.rate_limit_remaining = rate_limit.remaining
        result.rate_limit_reset_at = rate_limit.reset_at

    async def _generate_introductions(self, repos: list[Repository]) -> tuple[int, str | None]:
        """按批次为缺介绍的新仓库生成中文简介。

        逐仓库拉 README（失败则该仓库退化为只用元信息），再整批交给
        :func:`generate_introductions_resilient`；批次内个别失败由调用方计数。
        一旦遇到鉴权错误立刻停止后续批次：换模型、拆批、去掉 README 都无法修复
        401/密钥缺失，继续调用只会浪费额度并拖长任务。

        Args:
            repos: 需要生成介绍的仓库 ORM 对象列表。

        Returns:
            ``(缺失数量, 错误码)``；全部成功时错误码为 ``None``。
            错误码为 ``INTRO_AUTH_FAILED`` 或 ``INTRO_GENERATION_FAILED``，
            会被拼进 ``collection_runs.error_summary`` 供前端显示警告。
        """
        if not repos:
            return 0, None
        from app.services.introduction_service import (
            IntroductionAuthError,
            brief_from_repository,
            generate_introductions_resilient,
        )

        batch_size = settings.intro_batch_size
        failed = 0
        for start in range(0, len(repos), batch_size):
            batch = repos[start : start + batch_size]
            briefs = []
            for repo in batch:
                try:
                    readme = await self.github_client.get_readme(repo.full_name)
                except GitHubError as exc:
                    logger.warning("readme fetch failed for %s: %s", repo.full_name, exc)
                    readme = None
                briefs.append(brief_from_repository(repo, readme=readme))
            try:
                texts = await generate_introductions_resilient(briefs)
            except IntroductionAuthError as exc:
                logger.warning("skipping remaining introductions: %s", exc)
                return failed + len(repos) - start, "INTRO_AUTH_FAILED"
            for repo, text in zip(batch, texts):
                if text:
                    await self.repository_store.update_introduction(repo.github_id, text)
                else:
                    failed += 1
        return failed, "INTRO_GENERATION_FAILED" if failed else None

    def _eligible(self, repo: GitHubRepository) -> bool:
        """过滤归档、禁用与 fork 仓库。

        Returns:
            三类仓库都返回 ``False``，调用方会计入 ``failed_count`` 并跳过落库，
            避免榜单里出现“已停止维护”或“只是复制”的项目。
        """
        return not (repo.archived or repo.disabled or repo.fork)

    async def _finish(
        self,
        run: CollectionRun,
        result: CollectionResult,
        *,
        status: str,
    ) -> None:
        """写入任务终态字段并提交。

        这是本轮采集的最后一个事务边界：即使前面已经 commit 过仓库与榜单，
        任务状态也需要单独提交，前端轮询才能读到 ``SUCCESS`` / ``PARTIAL`` / ``FAILED``。

        Args:
            run: 本轮任务对象。
            result: 汇总后的计数与错误摘要。
            status: 终态，由调用方按分支决定（成功、部分成功或失败）。
        """
        await self.run_store.finish(
            run,
            status=status,
            query_count=result.period_count,
            discovered_count=result.discovered_count,
            updated_count=result.updated_count,
            failed_count=result.failed_count,
            rate_limit_remaining=result.rate_limit_remaining,
            rate_limit_reset_at=result.rate_limit_reset_at,
            error_summary=result.error_summary,
        )
        await self.session.commit()


def _error_summary(exc: Exception) -> str:
    """生成 ``异常类名: 消息`` 形式的摘要写进任务记录。

    只用于服务端排查与固定文案映射（``/api/v1/stats`` 会把关键字换成用户提示），
    因此这里可以带消息文本；调用方不要把它直接回给浏览器。

    Args:
        exc: 导致本轮失败的异常。

    Returns:
        单行摘要。
    """
    return f"{type(exc).__name__}: {exc}"
