import os
from pathlib import Path

import pytest
import sqlalchemy as sa

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set",
)


@pytest.fixture()
async def engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        for table in (
            "trending_entries",
            "star_snapshots",
            "collection_runs",
            "repositories",
            "last30days_reports",
        ):
            await conn.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))
        await conn.execute(sa.text(SCHEMA_PATH.read_text(encoding="utf-8")))
    yield engine
    await engine.dispose()


async def test_schema_creates_all_tables(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() ORDER BY table_name"
            )
        )
        tables = {row[0] for row in result.fetchall()}
    assert tables == {
        "collection_runs",
        "last30days_reports",
        "repositories",
        "star_snapshots",
        "trending_entries",
    }


async def test_schema_has_expected_indexes(engine) -> None:
    expected = {
        "uk_repositories_github_id",
        "uk_repositories_full_name",
        "uk_star_snapshots_repository_date",
        "uk_trending_entries_period_repo",
    }
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT index_name, table_name FROM information_schema.statistics "
                "WHERE table_schema = DATABASE()"
            )
        )
        indexes = {row[0] for row in result.fetchall()}
    assert expected.issubset(indexes)


async def test_schema_foreign_key_on_snapshots(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT constraint_name FROM information_schema.referential_constraints "
                "WHERE constraint_schema = DATABASE() AND constraint_name IN ("
                "'fk_star_snapshots_repository', 'fk_trending_entries_repository')"
            )
        )
        constraints = {row[0] for row in result.fetchall()}
    assert constraints == {
        "fk_star_snapshots_repository",
        "fk_trending_entries_repository",
    }
