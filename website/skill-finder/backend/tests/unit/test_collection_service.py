"""采集编排 `CollectionService.run` 的筛选、降级与结束状态。

被测链路是「抓日/周/月榜 → AI 关键词过滤 → GitHub API 补全 → 写库 → 记任务结果」，
本模块锁定三类语义：

- 每个周期按 Star 增量取 Top N，跨周期按 `full_name` 去重后只补全一次；
- 降级：单周期抓取失败、单仓库补全失败、某周期补全后一个都不剩（此时保留上一轮
  榜单而不是写空表）都只降为 `PARTIAL`；只有鉴权、限流依次向上抛；
- 中文简介开启时，认证失败立刻终止后续批次并记 `INTRO_AUTH_FAILED`，返回内容缺失
  则记 `INTRO_GENERATION_FAILED`，两种情况都保住已抓到的榜单。

隔离方式：爬虫、GitHub 客户端、四个仓储和数据库会话全部由本文件的 `Fake*` 替身承担
（`FakeGitHubClient` 继承真实类，只覆盖三个网络方法），既不联网也不连库；
`disable_introductions` 以 autouse 方式默认关掉简介生成，避免开发者本机 `.env` 里的
`INTRO_ENABLED` 改变离线断言，需要覆盖简介分支的用例会自行打开。
"""

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
    """默认关闭中文简介生成，让每条用例都从确定的“无简介”状态起步。

    autouse 是为了防止本机 `backend/.env` 打开 `INTRO_ENABLED` 后，采集会去调用真实
    模型服务；需要覆盖简介分支的用例自己再 monkeypatch 打开并替换生成函数。
    """
    from app.collector import service as collector_service

    monkeypatch.setattr(collector_service.settings, "intro_enabled", False)


def make_trending(
    owner: str,
    name: str,
    gained: int = 100,
    description: str = "An agent framework",
) -> TrendingRepository:
    """构造一条榜单页解析结果，字段与 `TrendingScraper` 的真实产出一致。

    默认描述含 “An agent framework”，因此默认就能通过 `ai_keywords="agent"` 的过滤；
    需要制造被过滤掉的样本时传 `description="Just a tool"` 之类的描述。
    """
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
    """构造一条 GitHub API 补全结果。

    `archived` / `disabled` / `fork` 用来覆盖“不合格仓库被跳过”的分支；`topics`
    默认 `["ai-agent"]`，保证分类规则稳定命中 AGENT，从而让断言专注在采集流程上。
    """
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
    """只记录是否 commit 的会话替身。

    采集要求在写榜单前先提交 `RUNNING`，好让其他连接查得到这次任务；
    提交时序就靠这个标记断言。
    """

    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeRepositoryStore:
    """仓库仓储替身：记录 upsert 与中文简介写回。

    `upsert` 返回的对象只需带采集后续要用到的字段，因此用 `SimpleNamespace`
    模拟落库后的 ORM 行，避免依赖真实模型。
    """

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
    """快照仓储替身：记录每日 Star 写入的（仓库 id、业务日期、总 Star）。"""

    def __init__(self) -> None:
        self.writes: list[tuple[int, object, int]] = []

    async def upsert_daily(self, repository_id, snapshot_date, stars_count):
        self.writes.append((repository_id, snapshot_date, stars_count))


class FakeTrendingStore:
    """榜单仓储替身：记录每个周期的整表替换调用。

    用替换而不是逐条写入，因此用例可以直接断言“哪个周期被写过、写了几条、排名如何”，
    也能验证补全后一个都不剩时该周期根本不出现（保留上一轮数据）。
    """

    def __init__(self) -> None:
        self.replaced: list[tuple[str, list, datetime]] = []

    async def replace_period(self, period, entries, fetched_at):
        self.replaced.append((period, list(entries), fetched_at))


class FakeRunStore:
    """任务仓储替身：自增 run id，并记录结束时的状态与摘要。"""

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
    """榜单爬虫替身：按周期返回预置结果，`failures` 中的周期抛抓取错误。

    `fetched` 记录请求过的周期，既能断言“三个周期都被请求”，也能验证全失败时应抛
    `TrendingScrapeError`。
    """

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
    """GitHub API 替身：继承真实客户端以复用构造与重试参数，只覆盖三个网络方法。

    `retry_delays` 全部置 0，避免用例在失败分支上真的等待退避；`repo_lookup` 的值可以
    是 `None`（API 返回 404 之类），`failures` 则用来抛指定的异常类型。
    """

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
    """为一批 full_name 生成补全结果，id 从 1 递增，省去每个用例手写字典。"""
    return {name: make_repo(index, name) for index, name in enumerate(names, start=1)}


def make_service(
    scraper: FakeScraper,
    github: FakeGitHubClient,
    *,
    top_n: int = 10,
    ai_keywords: str = "agent",
) -> CollectionService:
    """组装被测服务：全部依赖都是本文件的替身，只有参数按用例需要调整。

    `top_n` 用于验证“每周期截断”，`ai_keywords` 用默认值 `agent` 让 AI 过滤生效；
    服务把替身存成同名属性（如 `service.trending_store`），用例据此读取记录。
    """
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


async def test_running_status_is_committed_before_network_collection() -> None:
    from unittest.mock import AsyncMock

    scraper = FakeScraper()
    service = make_service(scraper, FakeGitHubClient())

    async def fetch(period):
        assert service.session.committed, "RUNNING 必须先提交，其他连接才能查询到任务"
        return []

    scraper.fetch = AsyncMock(side_effect=fetch)
    await service.run()
    assert scraper.fetch.await_count == 3


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


async def test_all_api_enrichment_failures_preserve_the_previous_period() -> None:
    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-flaky")]})
    github = FakeGitHubClient(failures={"acme/agent-flaky": GitHubRequestError("offline")})
    service = make_service(scraper, github)
    result = await service.run()
    assert result.status == "PARTIAL"
    assert "daily" not in [period for period, _, _ in service.trending_store.replaced]


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


async def test_intro_auth_failure_keeps_rankings_and_skips_remaining_batches(monkeypatch):
    from unittest.mock import AsyncMock

    from app.collector import service as collector_service
    from app.services import introduction_service

    monkeypatch.setattr(collector_service.settings, "intro_enabled", True)
    monkeypatch.setattr(collector_service.settings, "intro_batch_size", 5)
    # 兼容未提供专用 IntroductionAuthError 的旧实现：退化成通用生成错误后，
    # “认证失败即停止后续批次”的语义仍必须成立。
    auth_error = getattr(
        introduction_service, "IntroductionAuthError", introduction_service.IntroductionGenerationError
    )
    generate = AsyncMock(side_effect=auth_error("简介服务认证失败"))
    monkeypatch.setattr(introduction_service, "generate_introductions", generate)
    names = [f"acme/agent-{i}" for i in range(7)]
    scraper = FakeScraper(pages={"daily": [make_trending("acme", f"agent-{i}") for i in range(7)]})
    service = make_service(scraper, FakeGitHubClient(repo_lookup=default_lookup(*names)))
    result = await service.run()
    assert result.status == "PARTIAL"
    assert "INTRO_AUTH_FAILED" in result.error_summary
    assert result.updated_count == 7
    assert service.trending_store.replaced
    generate.assert_awaited_once()


async def test_missing_generated_text_marks_collection_partial(monkeypatch):
    from unittest.mock import AsyncMock

    from app.collector import service as collector_service
    from app.services import introduction_service

    monkeypatch.setattr(collector_service.settings, "intro_enabled", True)
    monkeypatch.setattr(
        introduction_service, "generate_introductions_resilient", AsyncMock(return_value=[None])
    )
    scraper = FakeScraper(pages={"daily": [make_trending("acme", "agent-a")]})
    service = make_service(scraper, FakeGitHubClient(repo_lookup=default_lookup("acme/agent-a")))
    result = await service.run()
    assert result.status == "PARTIAL"
    assert "INTRO_GENERATION_FAILED" in result.error_summary
    assert service.trending_store.replaced
