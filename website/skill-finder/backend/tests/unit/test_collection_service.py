from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.collector.github_client import (
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubRepository,
    GitHubRequestError,
)
from app.collector.service import CollectionService
from app.collector.trending import TrendingRepository, TrendingScrapeError


@pytest.fixture(autouse=True)
def disable_introductions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep collection tests independent of the local .env INTRO_ENABLED value."""
    from app.collector import service as collector_service

    monkeypatch.setattr(collector_service.settings, "intro_enabled", False)


def make_trending(
    owner: str,
    name: str,
    gained: int = 100,
    description: str = "An agent framework",
) -> TrendingRepository:
    return TrendingRepository(
        owner=owner,
        name=name,
        full_name=f"{owner}/{name}",
        description=description,
        language="Python",
        stars_total=5000,
        stars_gained=gained,
        rank=1,
    )


def make_repo(
    github_id: int,
    full_name: str,
    stars: int = 5000,
    archived: bool = False,
    disabled: bool = False,
    fork: bool = False,
    topics: list[str] | None = None,
) -> GitHubRepository:
    owner, name = full_name.split("/")
    return GitHubRepository(
        github_id=github_id,
        owner=owner,
        name=name,
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
        homepage=None,
        description="An agent framework",
        language="Python",
        topics=topics or ["ai-agent"],
        stars_count=stars,
        forks_count=10,
        open_issues_count=1,
        archived=archived,
        disabled=disabled,
        fork=fork,
        github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        github_updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeRepositoryStore:
    def __init__(self) -> None:
        self.upserted: list[tuple[GitHubRepository, object]] = []
        self.introductions: list[tuple[int, str]] = []

    async def upsert(self, repo, classification):
        self.upserted.append((repo, classification))
        return SimpleNamespace(
            id=repo.github_id,
            github_id=repo.github_id,
            introduction=None,
            full_name=repo.full_name,
            owner=repo.owner,
            name=repo.name,
            description=repo.description,
            language=repo.language,
            topics=list(repo.topics),
            stars_count=repo.stars_count,
            homepage=repo.homepage,
            html_url=repo.html_url,
        )

    async def update_introduction(self, github_id, text):
        self.introductions.append((github_id, text))


class FakeSnapshotStore:
    def __init__(self) -> None:
        self.writes: list[tuple[int, object, int]] = []

    async def upsert_daily(self, repository_id, snapshot_date, stars_count):
        self.writes.append((repository_id, snapshot_date, stars_count))


class FakeTrendingStore:
    def __init__(self) -> None:
        self.replaced: list[tuple[str, list, datetime]] = []

    async def replace_period(self, period, entries, fetched_at):
        self.replaced.append((period, list(entries), fetched_at))


class FakeRunStore:
    def __init__(self) -> None:
        self.finished: list[dict] = []
        self._next_id = 1

    async def create(self, trigger_type):
        run = SimpleNamespace(id=self._next_id, trigger_type=trigger_type)
        self._next_id += 1
        return run

    async def finish(self, run, **kwargs):
        self.finished.append({"run_id": run.id, **kwargs})


class FakeScraper:
    def __init__(
        self,
        pages: dict[str, list[TrendingRepository]] | None = None,
        failures: set[str] | None = None,
    ) -> None:
        self.pages = pages or {}
        self.failures = failures or set()
        self.fetched: list[str] = []

    async def fetch(self, period: str) -> list[TrendingRepository]:
        self.fetched.append(period)
        if period in self.failures:
            raise TrendingScrapeError(f"{period} unavailable")
        return list(self.pages.get(period, []))


class FakeGitHubClient(GitHubClient):
    def __init__(
        self,
        repo_lookup: dict[str, GitHubRepository | None] | None = None,
        failures: dict[str, type[Exception]] | None = None,
    ) -> None:
        super().__init__(token="test-token", retry_delays=(0.0, 0.0, 0.0))
        self.repo_lookup = repo_lookup or {}
        self.failures = failures or {}
        self.readmes: dict[str, str | None] = {}
        self.looked_up: list[str] = []

    async def get_repository(self, full_name):
        self.looked_up.append(full_name)
        if full_name in self.failures:
            raise self.failures[full_name]
        return self.repo_lookup.get(full_name)

    async def get_readme(self, full_name):
        return self.readmes.get(full_name)

    async def get_rate_limit(self):
        return SimpleNamespace(remaining=4999, reset_at=datetime(2026, 8, 10, tzinfo=UTC))


def default_lookup(*names: str) -> dict[str, GitHubRepository]:
    return {name: make_repo(index, name) for index, name in enumerate(names, start=1)}


def make_service(
    scraper: FakeScraper,
    github: FakeGitHubClient,
    *,
    top_n: int = 10,
    ai_keywords: str = "agent",
) -> CollectionService:
    return CollectionService(
        scraper=scraper,
        github_client=github,
        repository_store=FakeRepositoryStore(),
        snapshot_store=FakeSnapshotStore(),
        trending_store=FakeTrendingStore(),
        run_store=FakeRunStore(),
        session=FakeSession(),
        top_n=top_n,
        ai_keywords=ai_keywords,
        trigger_type="manual",
    )


async def test_collects_top_n_per_period_and_deduplicates() -> None:
    shared = make_trending("openai", "agents", gained=900)
    scraper = FakeScraper(
        pages={
            "daily": [shared, make_trending("acme", "mcp-tools", gained=500)],
            "weekly": [shared],
            "monthly": [make_trending("acme", "skill-hub", gained=300)],
        }
    )
    github = FakeGitHubClient(
        repo_lookup=default_lookup("openai/agents", "acme/mcp-tools", "acme/skill-hub")
    )
    service = make_service(scraper, github)

    result = await service.run()

    assert result.status == "SUCCESS"
    assert result.period_count == 3
    assert result.discovered_count == 4
    assert result.updated_count == 3
    assert result.failed_count == 0
    assert github.looked_up == ["openai/agents", "acme/mcp-tools", "acme/skill-hub"]

    periods = {period: entries for period, entries, _ in service.trending_store.replaced}
    assert [e.rank_position for e in periods["daily"]] == [1, 2]
    assert [e.stars_gained for e in periods["daily"]] == [900, 500]
    assert [e.rank_position for e in periods["monthly"]] == [1]
    assert len(periods["weekly"]) == 1
    assert service.session.committed is True


async def test_respects_top_n_and_ai_filter() -> None:
    scraper = FakeScraper(
        pages={
            "daily": [
                make_trending("acme", "agent-a", gained=100),
                make_trending("acme", "agent-b", gained=200),
                make_trending("acme", "plain-tool", gained=300, description="Just a tool"),
                make_trending("acme", "agent-c", gained=50),
            ]
        }
    )
    github = FakeGitHubClient(
        repo_lookup=default_lookup("acme/agent-a", "acme/agent-b", "acme/agent-c")
    )
    service = make_service(scraper, github, top_n=2)

    await service.run()

    assert github.looked_up == ["acme/agent-b", "acme/agent-a"]


async def test_partial_when_one_period_fails() -> None:
    scraper = FakeScraper(
        pages={
            "daily": [make_trending("acme", "agent-a")],
            "weekly": [make_trending("acme", "agent-b")],
        },
        failures={"monthly"},
    )
    github = FakeGitHubClient(
        repo_lookup=default_lookup("acme/agent-a", "acme/agent-b")
    )
    service = make_service(scraper, github)

    result = await service.run()

    assert result.status == "PARTIAL"
    assert result.error_summary is not None and "monthly" in result.error_summary
    written_periods = [period for period, _, _ in service.trending_store.replaced]
    assert written_periods == ["daily", "weekly"]
    assert service.run_store.finished[0]["status"] == "PARTIAL"


async def test_all_periods_failing_marks_run_failed() -> None:
    scraper = FakeScraper(failures={"daily", "weekly", "monthly"})
    github = FakeGitHubClient()
    service = make_service(scraper, github)

    with pytest.raises(TrendingScrapeError):
        await service.run()

    assert service.run_store.finished[0]["status"] == "FAILED"
    assert "TrendingScrapeError" in service.run_store.finished[0]["error_summary"]


async def test_failed_enrichment_is_counted_and_skipped() -> None:
    scraper = FakeScraper(
        pages={
            "daily": [
                make_trending("acme", "agent-ok", gained=100),
                make_trending("acme", "agent-flaky", gained=90),
                make_trending("acme", "agent-gone", gained=80),
            ]
        }
    )
    github = FakeGitHubClient(
        repo_lookup={"acme/agent-ok": make_repo(1, "acme/agent-ok"), "acme/agent-gone": None},
        failures={"acme/agent-flaky": GitHubRequestError("boom")},
    )
    service = make_service(scraper, github)

    result = await service.run()

    assert result.status == "PARTIAL"
    assert result.failed_count == 2
    assert result.updated_count == 1
    entries = service.trending_store.replaced[0][1]
    assert [entry.repository_id for entry in entries] == [1]


async def test_ineligible_repositories_are_skipped() -> None:
    scraper = FakeScraper(
        pages={
            "daily": [
                make_trending("acme", "agent-fork", gained=300),
                make_trending("acme", "agent-archived", gained=200),
                make_trending("acme", "agent-ok", gained=100),
            ]
        }
    )
    github = FakeGitHubClient(
        repo_lookup={
            "acme/agent-fork": make_repo(1, "acme/agent-fork", fork=True),
            "acme/agent-archived": make_repo(2, "acme/agent-archived", archived=True),
            "acme/agent-ok": make_repo(3, "acme/agent-ok"),
        }
    )
    service = make_service(scraper, github)

    result = await service.run()

    assert result.failed_count == 2
    assert [repo.github_id for repo, _ in service.repository_store.upserted] == [3]
    entries = service.trending_store.replaced[0][1]
    assert [entry.repository_id for entry in entries] == [3]


async def test_auth_failure_marks_failed_and_reraises() -> None:
    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-a")]})
    github = FakeGitHubClient(
        failures={"acme/agent-a": GitHubAuthError("bad token")}
    )
    service = make_service(scraper, github)

    with pytest.raises(GitHubAuthError):
        await service.run()

    assert service.run_store.finished[0]["status"] == "FAILED"
    assert "GitHubAuthError" in service.run_store.finished[0]["error_summary"]


async def test_rate_limit_marks_failed_and_reraises() -> None:
    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-a")]})
    github = FakeGitHubClient(
        failures={
            "acme/agent-a": GitHubRateLimitError(datetime(2026, 8, 10, tzinfo=UTC))
        }
    )
    service = make_service(scraper, github)

    with pytest.raises(GitHubRateLimitError):
        await service.run()

    assert service.run_store.finished[0]["status"] == "FAILED"


async def test_generates_introductions_with_readme(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.collector import service as collector_service
    from app.services import introduction_service

    monkeypatch.setattr(collector_service.settings, "intro_enabled", True)
    captured: dict[str, list] = {}

    async def fake_generate(briefs, **kwargs):
        captured["briefs"] = list(briefs)
        return [
            json.dumps({"introduction": f"中文简介 {brief.name}"}, ensure_ascii=False)
            for brief in briefs
        ]

    monkeypatch.setattr(introduction_service, "generate_introductions", fake_generate)

    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-a")]})
    github = FakeGitHubClient(repo_lookup=default_lookup("acme/agent-a"))
    github.readmes["acme/agent-a"] = "# Agent A\n\nnpm install"
    service = make_service(scraper, github)

    result = await service.run()

    assert result.status == "SUCCESS"
    assert captured["briefs"][0].readme == "# Agent A\n\nnpm install"
    assert service.repository_store.introductions == [
        (1, json.dumps({"introduction": "中文简介 agent-a"}, ensure_ascii=False))
    ]


async def test_writes_daily_snapshot_for_business_date() -> None:
    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-a")]})
    github = FakeGitHubClient(repo_lookup=default_lookup("acme/agent-a"))
    service = make_service(scraper, github)

    result = await service.run()

    assert service.snapshot_store.writes[0][1] == service._business_date
    assert service.snapshot_store.writes[0][2] == 5000
    assert result.status == "SUCCESS"
    assert result.rate_limit_remaining == 4999
