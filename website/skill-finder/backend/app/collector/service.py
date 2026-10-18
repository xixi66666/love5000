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

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"


@dataclass
class CollectionResult:
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
        self._timezone = ZoneInfo(self.business_timezone)
        self._selected: dict[str, list[TrendingRepository]] = {}

    @property
    def _business_date(self) -> date:
        return datetime.now(self._timezone).date()

    async def run(self) -> CollectionResult:
        run = await self.run_store.create(self.trigger_type)
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

        await self._generate_introductions(intro_pending)
        await self._record_rate_limit(result)
        await self.session.commit()

    async def _record_rate_limit(self, result: CollectionResult) -> None:
        rate_limit = await self.github_client.get_rate_limit()
        result.rate_limit_remaining = rate_limit.remaining
        result.rate_limit_reset_at = rate_limit.reset_at

    async def _generate_introductions(self, repos: list[Repository]) -> None:
        if not repos:
            return
        from app.services.introduction_service import (
            brief_from_repository,
            generate_introductions_resilient,
        )

        batch_size = settings.intro_batch_size
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
            texts = await generate_introductions_resilient(briefs)
            for repo, text in zip(batch, texts):
                if text:
                    await self.repository_store.update_introduction(repo.github_id, text)

    def _eligible(self, repo: GitHubRepository) -> bool:
        return not (repo.archived or repo.disabled or repo.fork)

    async def _finish(
        self,
        run: CollectionRun,
        result: CollectionResult,
        *,
        status: str,
    ) -> None:
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
    return f"{type(exc).__name__}: {exc}"
