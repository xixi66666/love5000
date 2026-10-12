import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.collector.classifier import Classification
from app.collector.github_client import GitHubRepository
from app.repositories.collection_runs import CollectionRunStore
from app.repositories.repositories import RepositoryStore
from app.repositories.snapshots import SnapshotStore
from app.repositories.trending import TrendingEntryValue, TrendingStore

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set",
)


def make_repo(github_id: int, full_name: str, stars: int = 150) -> GitHubRepository:
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


async def test_repository_store_upsert_and_available(session: AsyncSession) -> None:
    store = RepositoryStore(session)
    classification = Classification(categories=("AGENT",), matched_rules=("topic:ai-agent",))

    first = await store.upsert(make_repo(1, "a/repo"), classification)
    assert first.id > 0
    assert first.github_id == 1

    second = await store.upsert(make_repo(1, "a/repo", stars=200), classification)
    assert second.id == first.id
    assert second.stars_count == 200

    available = await store.list_available()
    assert [r.github_id for r in available] == [1]

    await store.mark_unavailable([1])
    await session.commit()
    available_after = await store.list_available()
    assert available_after == []


async def test_repository_store_replaces_recreated_repository_identity(
    session: AsyncSession,
) -> None:
    store = RepositoryStore(session)
    classification = Classification(categories=("AGENT",), matched_rules=("topic:ai-agent",))

    original = await store.upsert(make_repo(10, "owner/reused-name"), classification)
    recreated = await store.upsert(
        make_repo(11, "owner/reused-name", stars=300), classification
    )

    assert recreated.id == original.id
    assert recreated.github_id == 11
    assert recreated.stars_count == 300
    assert [repository.github_id for repository in await store.list_available()] == [11]


async def test_snapshot_store_upsert_conflicts(session: AsyncSession) -> None:
    repo_store = RepositoryStore(session)
    classification = Classification(categories=("MCP",), matched_rules=("topic:mcp-server",))
    repo = await repo_store.upsert(make_repo(2, "b/mcp"), classification)

    snapshot_store = SnapshotStore(session)
    await snapshot_store.upsert_daily(repo.id, date(2026, 8, 1), 100)
    await session.commit()

    await snapshot_store.upsert_daily(repo.id, date(2026, 8, 1), 120)
    await session.commit()

    result = await session.execute(
        sa.text(
            "SELECT stars_count FROM star_snapshots "
            "WHERE repository_id = :rid AND snapshot_date = '2026-08-01'"
        ),
        {"rid": repo.id},
    )
    assert result.scalar() == 120


async def test_trending_store_replaces_period(session: AsyncSession) -> None:
    repo_store = RepositoryStore(session)
    classification = Classification(categories=("SKILL",), matched_rules=("topic:agent-skills",))
    repo = await repo_store.upsert(make_repo(3, "c/skill-hub"), classification)

    store = TrendingStore(session)
    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    await store.replace_period(
        "daily", [TrendingEntryValue(repo.id, 1, 321, 900)], fetched_at
    )
    await session.commit()

    rows = await session.execute(
        sa.text("SELECT stars_gained FROM trending_entries WHERE period = 'daily'")
    )
    assert rows.scalar() == 321

    await store.replace_period("daily", [], fetched_at)
    await session.commit()
    remaining = await session.execute(sa.text("SELECT COUNT(*) FROM trending_entries"))
    assert remaining.scalar() == 0


async def test_collection_run_store_lifecycle(session: AsyncSession) -> None:
    store = CollectionRunStore(session)
    run = await store.create("manual")
    assert run.status == "RUNNING"
    assert run.id > 0

    await store.finish(
        run,
        status="SUCCESS",
        query_count=7,
        discovered_count=3,
        updated_count=2,
        failed_count=0,
        rate_limit_remaining=4500,
        rate_limit_reset_at=None,
        error_summary=None,
    )
    await session.commit()

    latest = await store.latest()
    assert latest.id == run.id
    assert latest.status == "SUCCESS"
    assert latest.discovered_count == 3
