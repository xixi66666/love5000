import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.collector.classifier import Classification
from app.collector.github_client import GitHubRepository
from app.repositories.repositories import RepositoryStore
from app.repositories.trending import TrendingEntryValue, TrendingStore
from app.schemas.common import PageParams
from app.services.repository_service import RepositoryService

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set",
)


def make_repo(github_id: int, full_name: str, stars: int, language: str = "Python") -> GitHubRepository:
    owner, name = full_name.split("/")
    return GitHubRepository(
        github_id=github_id,
        owner=owner,
        name=name,
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
        homepage=None,
        description="An agent framework",
        language=language,
        topics=["ai-agent"],
        stars_count=stars,
        forks_count=5,
        open_issues_count=1,
        archived=False,
        disabled=False,
        fork=False,
        github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        github_updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


@pytest.fixture()
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        for table in (
            "trending_entries",
            "star_snapshots",
            "collection_runs",
            "repositories",
        ):
            await conn.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))
        await conn.execute(sa.text(SCHEMA_PATH.read_text(encoding="utf-8")))
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def seed(session: AsyncSession) -> dict[str, int]:
    repo_store = RepositoryStore(session)
    trending_store = TrendingStore(session)
    ids: dict[str, int] = {}
    data = [
        ("agent-a", "a/agent-a", 1000, "Python", ("AGENT",)),
        ("agent-b", "b/agent-b", 900, "Python", ("AGENT",)),
        ("mcp-c", "c/mcp-c", 800, "TypeScript", ("MCP",)),
        ("skill-d", "d/skill-d", 700, "Python", ("SKILL",)),
    ]
    for index, (key, full_name, stars, language, categories) in enumerate(data, start=1):
        repo = await repo_store.upsert(
            make_repo(index, full_name, stars, language),
            Classification(categories=categories, matched_rules=(f"topic:{key}",)),
        )
        ids[key] = repo.id

    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    await trending_store.replace_period(
        "daily",
        [
            TrendingEntryValue(ids["agent-a"], 1, 120, 1000),
            TrendingEntryValue(ids["skill-d"], 2, 30, 700),
        ],
        fetched_at,
    )
    await trending_store.replace_period(
        "weekly",
        [TrendingEntryValue(ids["agent-a"], 1, 450, 1000)],
        fetched_at,
    )
    await trending_store.replace_period(
        "monthly",
        [
            TrendingEntryValue(ids["mcp-c"], 1, 900, 800),
            TrendingEntryValue(ids["agent-a"], 2, 700, 1000),
        ],
        fetched_at,
    )
    await session.commit()
    return ids


async def test_ranking_daily_growth_order(session: AsyncSession) -> None:
    await seed(session)
    service = RepositoryService(business_timezone="Asia/Shanghai")
    result = await service.list_repositories(
        session,
        PageParams(page=1, page_size=20),
        sort="daily_stars",
        category=None,
        language=None,
        min_stars=None,
        q=None,
    )
    names = [item.name for item in result["items"]]
    assert names[0] == "agent-a"
    assert names[1] == "skill-d"
    assert result["total"] == 4
    agent_a = next(i for i in result["items"] if i.name == "agent-a")
    assert agent_a.daily_stars == 120
    assert agent_a.weekly_stars == 450
    assert agent_a.monthly_stars == 700


async def test_ranking_monthly_sort(session: AsyncSession) -> None:
    await seed(session)
    service = RepositoryService(business_timezone="Asia/Shanghai")
    result = await service.list_repositories(
        session,
        PageParams(page=1, page_size=20),
        sort="monthly_stars",
        category=None,
        language=None,
        min_stars=None,
        q=None,
    )
    names = [item.name for item in result["items"]]
    assert names[0] == "mcp-c"
    assert names[1] == "agent-a"


async def test_ranking_repos_missing_period_sort_last(session: AsyncSession) -> None:
    await seed(session)
    service = RepositoryService(business_timezone="Asia/Shanghai")
    result = await service.list_repositories(
        session,
        PageParams(page=1, page_size=20),
        sort="daily_stars",
        category=None,
        language=None,
        min_stars=None,
        q=None,
    )
    agent_b = next(i for i in result["items"] if i.name == "agent-b")
    assert agent_b.daily_stars is None
    assert agent_b.weekly_stars is None
    assert result["items"][-1].name == "agent-b"


async def test_combined_filters(session: AsyncSession) -> None:
    await seed(session)
    service = RepositoryService(business_timezone="Asia/Shanghai")
    result = await service.list_repositories(
        session,
        PageParams(page=1, page_size=20),
        sort="total_stars",
        category="AGENT",
        language="Python",
        min_stars=None,
        q=None,
    )
    names = {item.name for item in result["items"]}
    assert names == {"agent-a", "agent-b"}

    searched = await service.list_repositories(
        session,
        PageParams(page=1, page_size=20),
        sort="total_stars",
        category=None,
        language=None,
        min_stars=None,
        q="mcp-c",
    )
    assert [i.name for i in searched["items"]] == ["mcp-c"]


async def test_pagination_stable(session: AsyncSession) -> None:
    await seed(session)
    service = RepositoryService(business_timezone="Asia/Shanghai")
    page1 = await service.list_repositories(
        session,
        PageParams(page=1, page_size=2),
        sort="total_stars",
        category=None,
        language=None,
        min_stars=None,
        q=None,
    )
    page2 = await service.list_repositories(
        session,
        PageParams(page=2, page_size=2),
        sort="total_stars",
        category=None,
        language=None,
        min_stars=None,
        q=None,
    )
    assert page1["total"] == 4
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    page1_ids = [i.id for i in page1["items"]]
    page2_ids = [i.id for i in page2["items"]]
    assert not set(page1_ids) & set(page2_ids)
