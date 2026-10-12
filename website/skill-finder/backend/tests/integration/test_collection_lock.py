import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set",
)

LOCK_NAME = "skill_finder_collection"


@pytest.fixture()
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=sa.pool.NullPool)
    yield engine
    import asyncio

    try:
        asyncio.get_event_loop().run_until_complete(engine.dispose())
    except RuntimeError:
        asyncio.run(engine.dispose())


async def test_only_one_connection_acquires_lock(engine) -> None:
    conn_a = await engine.connect()
    conn_b = await engine.connect()
    try:
        result_a = await conn_a.execute(sa.text(f"SELECT GET_LOCK('{LOCK_NAME}', 0)"))
        assert result_a.scalar() == 1

        result_b = await conn_b.execute(sa.text(f"SELECT GET_LOCK('{LOCK_NAME}', 0)"))
        assert result_b.scalar() == 0

        await conn_a.execute(sa.text(f"SELECT RELEASE_LOCK('{LOCK_NAME}')"))
        result_b_again = await conn_b.execute(
            sa.text(f"SELECT GET_LOCK('{LOCK_NAME}', 0)")
        )
        assert result_b_again.scalar() == 1
    finally:
        await conn_b.execute(sa.text(f"SELECT RELEASE_LOCK('{LOCK_NAME}')"))
        await conn_a.close()
        await conn_b.close()
