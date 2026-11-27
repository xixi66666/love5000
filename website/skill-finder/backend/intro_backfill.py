"""一次性运维脚本：循环触发管理接口，把缺失的中文简介补齐。

流程：直连数据库统计 ``repositories.introduction IS NULL`` 的数量 → 调用
``POST /admin/introductions``（带 ``X-Admin-Key``）让后端补一批 → 睡 280 秒再统计，
直到没有缺失或达到 400 轮上限。脚本本身不生成简介，只负责“催”后端，因此可以随时
中断，重复运行也不会重复写入已存在的简介。

凭据：``ADMIN_KEY`` 与 ``DATABASE_URL`` 优先读环境变量，其次读同目录 ``.env``；
日志只记录数量与接口返回，不打印密钥或数据库连接串。
"""
import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 管理接口地址：指向本机 8000 端口，按实际部署改成本机 uvicorn 端口或域名。
BASE = "http://127.0.0.1:8000/api/v1"
# 同目录 .env 与追加日志；脚本可能在 app 包之外单独运行，所以不依赖 pydantic-settings。
ENV_FILE = Path(__file__).with_name(".env")
LOG = Path(__file__).with_name("intro_backfill.log")

# 极简 .env 解析：只认 KEY=VALUE，忽略注释行与不含等号的行，不处理引号与转义。
env_values: dict[str, str] = {}
for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        env_values[key.strip()] = value.strip()

# 环境变量优先于 .env；两者都缺失时 main 会直接报错退出，避免空密钥发请求。
admin_key = os.getenv("ADMIN_KEY") or env_values.get("ADMIN_KEY", "")
database_url = os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL", "")


def log(msg: str) -> None:
    """带时间戳同时输出到控制台与同目录日志文件。

    追加写入而不是覆盖，便于事后回看每一轮的数量变化；消息里不应包含密钥或连接串。

    Args:
        msg: 单行消息。
    """
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


async def count_missing() -> int:
    """统计还没有中文简介的仓库数量。

    每轮新建引擎并在结束时 ``dispose``，因此长时间运行的脚本不会积压连接。

    Returns:
        ``introduction IS NULL`` 的行数（包含已软删除的仓库，作为粗略进度指标）。
    """
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
    """请求后端补一批简介（每批 20 个）。

    同步阻塞的 urllib 调用，调用方用 ``asyncio.to_thread`` 包起来以免堵住事件循环；
    接口返回 202 后真正的生成在后台继续。
    """
    req = urllib.request.Request(
        f"{BASE}/admin/introductions?limit=20",
        method="POST",
        headers={"X-Admin-Key": admin_key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    log(f"triggered: {body}")


async def main() -> None:
    """主循环：统计缺失 → 触发一批 → 等待，直到补齐或达到轮次上限。

    280 秒的间隔是为了给后端后台生成留出时间，避免连续触发把上游模型打到限流。

    Raises:
        RuntimeError: ``ADMIN_KEY`` 或 ``DATABASE_URL`` 缺失。
    """
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
