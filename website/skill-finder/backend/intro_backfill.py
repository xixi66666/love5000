import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BASE = "http://127.0.0.1:8000/api/v1"
ENV_FILE = Path(__file__).with_name(".env")
LOG = Path(__file__).with_name("intro_backfill.log")

env_values: dict[str, str] = {}
for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        env_values[key.strip()] = value.strip()

admin_key = os.getenv("ADMIN_KEY") or env_values.get("ADMIN_KEY", "")
database_url = os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL", "")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


async def count_missing() -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT COUNT(*) FROM repositories WHERE introduction IS NULL")
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


def trigger_batch() -> None:
    req = urllib.request.Request(
        f"{BASE}/admin/introductions?limit=20",
        method="POST",
        headers={"X-Admin-Key": admin_key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    log(f"triggered: {body}")


async def main() -> None:
    if not admin_key or not database_url:
        raise RuntimeError("ADMIN_KEY and DATABASE_URL must be configured")

    rounds = 0
    while True:
        missing = await count_missing()
        log(f"round {rounds}: missing={missing}")
        if missing <= 0:
            log("all done")
            return
        await asyncio.to_thread(trigger_batch)
        rounds += 1
        if rounds >= 400:
            log("reached max rounds, stopping")
            return
        await asyncio.sleep(280)


if __name__ == "__main__":
    asyncio.run(main())
