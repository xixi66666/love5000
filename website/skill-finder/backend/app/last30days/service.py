"""调用用户级 last30days skill 并缓存 Top 20 排名。

运行时发现顺序：`LAST30DAYS_SKILL_DIR` → `~/.codex`、`~/.agents`、`~/.claude` 下的
`skills/last30days`；解释器取 `LAST30DAYS_PYTHON`、当前解释器、PATH 与 Codex 内置
运行时，并逐个用 `-c` 探测 Python 3.12+。子进程只继承基础系统变量、`LAST30DAYS_*`
和 skill 需要的来源凭据，本服务的数据库连接串、管理密钥与模型配置都不转发。

失败降级：找不到运行时返回 `unconfigured`，超时/非零退出/非法 JSON 返回 `error`，
这两类都不写库；刷新按方向持有 `asyncio.Lock`，避免同一方向并发跑两次研究。榜单
只保存实际取到的条目，按 engagement 求和降序取前 20。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.last30days_reports import Last30DaysReportStore

Direction = Literal["agent", "skill"]

DIRECTION_QUERIES: dict[str, str] = {
    "agent": "AI agents",
    "skill": "AI agent skills",
}

TOP_RANK_LIMIT = 20

_REFRESH_FETCH_LIMIT = 100

_DIRECTION_LOCKS: dict[str, asyncio.Lock] = {}


class Last30DaysNotConfigured(RuntimeError):
    """用户级 last30days skill 找不到入口或可用解释器时抛出。"""


class Last30DaysExecutionError(RuntimeError):
    """引擎超时、非零退出或返回无法解析的输出时抛出。"""


def _now_iso() -> str:
    """返回带 UTC 时区的 ISO 时间戳。"""
    return datetime.now(UTC).isoformat()


def _skill_entrypoint() -> Path:
    """定位已安装的 last30days 引擎入口脚本。

    先看 `LAST30DAYS_SKILL_DIR`，再依次尝试 `~/.codex`、`~/.agents`、`~/.claude`
    下的 `skills/last30days`；每个目录同时接受 `scripts/last30days.py` 和根目录的
    `last30days.py`，都不存在就失败，不内置第二套实现。

    Raises:
        Last30DaysNotConfigured: 所有候选目录都没有入口脚本。
    """
    configured = settings.last30days_skill_dir.strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home() / ".codex" / "skills" / "last30days",
            Path.home() / ".agents" / "skills" / "last30days",
            Path.home() / ".claude" / "skills" / "last30days",
        ]
    )
    for candidate in candidates:
        for relative_path in (Path("scripts") / "last30days.py", Path("last30days.py")):
            entrypoint = candidate / relative_path
            if entrypoint.is_file():
                return entrypoint
    raise Last30DaysNotConfigured(
        "未找到用户级 last30days skill，请安装到 ~/.codex/skills/last30days。"
    )


async def _supports_python312(executable: str) -> bool:
    """探测某个解释器是否为 Python 3.12 或更高。

    用返回码判断而不是解析版本字符串；5 秒超时、无法启动或非零退出都视为不支持。
    """
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            "-c",
            "import sys; raise SystemExit(sys.version_info < (3, 12))",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await asyncio.wait_for(process.wait(), timeout=5) == 0
    except (OSError, TimeoutError):
        return False


async def _python_executable() -> str:
    """挑选一个可用的 Python 3.12+ 解释器。

    顺序：`LAST30DAYS_PYTHON`、当前解释器（自身需 3.12+）、PATH 上的
    python3.14/3.13/3.12/3、以及 `~/.cache/codex-runtimes` 里的内置运行时；按路径
    规范化去重后逐个探测。

    Raises:
        Last30DaysNotConfigured: 没有任何候选满足版本要求。
    """
    configured = settings.last30days_python.strip()
    candidates: list[str] = []
    if configured:
        candidates.append(str(Path(configured).expanduser()))
    if sys.version_info >= (3, 12):
        candidates.append(sys.executable)
    for command in ("python3.14", "python3.13", "python3.12", "python3", "python"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)
    runtime_root = Path.home() / ".cache" / "codex-runtimes"
    if runtime_root.is_dir():
        candidates.extend(
            str(path)
            for path in sorted(runtime_root.glob("*/dependencies/python/python.exe"), reverse=True)
        )

    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if await _supports_python312(candidate):
            return candidate
    raise Last30DaysNotConfigured(
        "last30days 需要 Python 3.12 或更高版本；可通过 LAST30DAYS_PYTHON 指定解释器。"
    )


def _engine_environment() -> dict[str, str]:
    """构造传给引擎的最小环境变量集合。

    只保留基础系统变量、`LAST30DAYS_*` 与 skill 需要的来源凭据；本服务的数据库
    连接串、管理密钥和模型配置都不会进入子进程。强制 UTF-8 输出，避免 Windows
    控制台编码把 JSON 弄坏。
    """
    allowed_exact = {
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
    allowed_credentials = {
        "APIFY_API_TOKEN",
        "BRAVE_API_KEY",
        "EXA_API_KEY",
        "GITHUB_TOKEN",
        "PERPLEXITY_API_KEY",
        "SERPER_API_KEY",
        "TAVILY_API_KEY",
        "X_BEARER_TOKEN",
        "YOUTUBE_API_KEY",
    }
    environment: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in allowed_exact or upper in allowed_credentials or upper.startswith("LAST30DAYS_"):
            environment[key] = value
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


async def _run_last30days(arguments: list[str]) -> dict[str, Any]:
    """执行一次引擎调用并解析它的 JSON 输出。

    Args:
        arguments: 传给入口脚本的参数，例如主题、`--diagnose`。

    Returns:
        解析后的 JSON 对象。

    Raises:
        Last30DaysNotConfigured: 找不到入口脚本或可用解释器。
        Last30DaysExecutionError: 超时（先 kill 进程）、非零退出、输出不是 UTF-8
            JSON 或顶层不是对象；错误信息不回显引擎原始输出。
    """
    entrypoint = _skill_entrypoint()
    python = await _python_executable()
    process = await asyncio.create_subprocess_exec(
        python,
        str(entrypoint),
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_engine_environment(),
    )
    try:
        stdout, _stderr = await asyncio.wait_for(
            process.communicate(), timeout=settings.last30days_timeout_seconds
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise Last30DaysExecutionError("last30days 研究超时，请缩小主题后重试。") from exc
    if process.returncode != 0:
        raise Last30DaysExecutionError("last30days 引擎执行失败，请运行诊断后重试。")
    try:
        payload = json.loads(stdout.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Last30DaysExecutionError("last30days 引擎返回了无法解析的结果。") from exc
    if not isinstance(payload, dict):
        raise Last30DaysExecutionError("last30days 引擎返回格式不正确。")
    return payload


def _empty_response(status: str, message: str) -> dict[str, Any]:
    """构造任意主题研究的空结果，保留状态与可读提示。"""
    return {
        "status": status,
        "query": "",
        "items": [],
        "clusters": [],
        "sources": [],
        "source_status": {},
        "fetched_at": _now_iso(),
        "message": message,
    }


def _source_state(value: Any) -> str:
    """把来源状态字段归纳成一个字符串。

    引擎在不同版本里既可能给字符串，也可能给 `{"status": ...}` 对象；未知形状一律
    返回 `unknown`，由上层按降级来源处理。
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("status") or value.get("state") or "unknown")
    return "unknown"


async def fetch_last30days(query: str, limit: int = 50) -> dict[str, Any]:
    """运行任意主题的近 30 天研究，并把结果归一成前端可用的结构。

    Args:
        query: 研究主题，去空白后使用。
        limit: 最多返回多少条，默认 50。

    Returns:
        `Last30DaysResponse` 形状的字典。`status` 规则：没有任何条目时，有降级
        来源为 `error`，否则 `no-results`；有条目时，有降级来源为 `partial`，
        否则 `working`。模块禁用返回 `skipped`，运行时缺失返回 `unconfigured`。

    Notes:
        只要引擎能启动，单个来源失败不会抛异常，只体现在 `source_status` 与
        `message` 里；提示信息不含凭据与私有路径。
    """
    if not settings.last30days_enabled:
        return _empty_response("skipped", "last30days 模块已禁用。")

    clean_query = query.strip()
    arguments = [
        clean_query,
        "--emit=json",
        "--json-profile=agent",
        "--auto-resolve",
        "--save-suffix=skill-finder",
    ]
    if settings.last30days_memory_dir.strip():
        arguments.append(f"--save-dir={Path(settings.last30days_memory_dir).expanduser()}")
    try:
        payload = await _run_last30days(arguments)
    except Last30DaysNotConfigured as exc:
        response = _empty_response("unconfigured", str(exc))
        response["query"] = clean_query
        return response
    except Last30DaysExecutionError as exc:
        response = _empty_response("error", str(exc))
        response["query"] = clean_query
        return response

    raw_status = payload.get("source_status")
    source_status = raw_status if isinstance(raw_status, dict) else {}
    sources = sorted(str(source) for source in source_status)
    raw_items = payload.get("results")
    items = raw_items[:limit] if isinstance(raw_items, list) else []
    raw_clusters = payload.get("clusters")
    clusters = raw_clusters if isinstance(raw_clusters, list) else []
    degraded = [
        source
        for source, value in source_status.items()
        if _source_state(value) not in {"ok", "working", "no-results", "unavailable", "skipped"}
    ]
    if items:
        status = "partial" if degraded else "working"
    else:
        status = "error" if degraded else "no-results"
    message = f"部分来源不可用：{', '.join(degraded)}" if degraded else None
    return {
        "status": status,
        "query": str(payload.get("query") or clean_query),
        "items": items,
        "clusters": clusters,
        "sources": sources,
        "source_status": source_status,
        "fetched_at": str(payload.get("generated_at") or _now_iso()),
        "message": message,
    }


async def diagnose_last30days() -> dict[str, Any]:
    """调用引擎的 `--diagnose` 检查运行时与来源配置。

    Returns:
        `{"status", "sources", "message"}`；只有引擎自检通过才算 `working`，否则为
        `error` 并给出可读原因，不返回引擎原始输出。
    """
    if not settings.last30days_enabled:
        return {"status": "skipped", "sources": [], "message": "last30days 模块已禁用。"}
    try:
        payload = await _run_last30days(["--diagnose"])
    except Last30DaysNotConfigured as exc:
        return {"status": "unconfigured", "sources": [], "message": str(exc)}
    except Last30DaysExecutionError as exc:
        return {"status": "error", "sources": [], "message": str(exc)}
    sources = payload.get("available_sources")
    return {
        "status": "working" if payload.get("safe", True) else "error",
        "sources": [str(source) for source in sources] if isinstance(sources, list) else [],
        "message": None if payload.get("safe", True) else "last30days 诊断未通过。",
    }


def _engagement_total(engagement: Any) -> float:
    """把 engagement 字典里的数值求和；布尔和字符串不计入。"""
    if not isinstance(engagement, dict):
        return 0.0
    return float(
        sum(
            value
            for value in engagement.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
    )


def rank_items(items: list[Any], limit: int = TOP_RANK_LIMIT) -> list[dict[str, Any]]:
    """按 engagement 总和降序排序并截取前 `limit` 条。

    非字典条目直接丢弃，不让引擎的脏数据打断整份榜单；排序只依赖真实互动量，
    没有互动数据时保持引擎返回顺序。
    """
    valid = [item for item in items if isinstance(item, dict)]
    return sorted(
        valid, key=lambda item: _engagement_total(item.get("engagement")), reverse=True
    )[:limit]


def _empty_ranking(direction: str, status: str, message: str) -> dict[str, Any]:
    """构造某个方向的空榜单，保留状态与可读提示。"""
    return {
        "direction": direction,
        "status": status,
        "items": [],
        "clusters": [],
        "sources": [],
        "source_status": {},
        "fetched_at": "",
        "message": message,
    }


def _parse_fetched_at(value: Any) -> datetime:
    """把引擎返回的抓取时间解析成不带时区的 UTC 时间，供数据库存储。

    缺失、非法或无法解析时退回当前时间；带时区的输入统一换算到 UTC，无时区的按
    UTC 解释。
    """
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            pass
        else:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).replace(tzinfo=None)
    return datetime.now(UTC).replace(tzinfo=None)


def _ranking_from_report(direction: str, report: Any) -> dict[str, Any]:
    """把数据库记录还原成榜单响应，缺失字段用空列表或空字典兜底。"""
    payload = report.payload if isinstance(report.payload, dict) else {}
    fetched_at = report.fetched_at
    if isinstance(fetched_at, datetime):
        fetched_iso = fetched_at.replace(tzinfo=UTC).isoformat()
    else:
        fetched_iso = str(fetched_at or "")
    return {
        "direction": direction,
        "status": report.status,
        "items": payload.get("items") or [],
        "clusters": payload.get("clusters") or [],
        "sources": payload.get("sources") or [],
        "source_status": payload.get("source_status") or {},
        "fetched_at": fetched_iso,
        "message": report.message,
    }


async def get_ranking(session: AsyncSession, direction: Direction) -> dict[str, Any]:
    """读取某个方向的缓存榜单。

    Returns:
        从未刷新时返回 `no-results` 空榜单；存储层异常（多数是还没执行最新的
        `schema.sql`）同样返回 `no-results`，但附带可读的初始化提示，不向页面抛栈。
    """
    try:
        report = await Last30DaysReportStore(session).get(direction)
    except SQLAlchemyError:
        return _empty_ranking(
            direction, "no-results", "榜单存储未初始化，请先执行最新的 schema.sql。"
        )
    if report is None:
        return _empty_ranking(
            direction, "no-results", "该方向还没有榜单数据，点击刷新按钮生成。"
        )
    return _ranking_from_report(direction, report)


async def refresh_ranking(session: AsyncSession, direction: Direction) -> dict[str, Any]:
    """同步跑一次研究并覆盖某个方向的 Top 20 榜单。

    同一方向用 `asyncio.Lock` 串行化，避免重复启动耗时的多源抓取。研究失败
    （`unconfigured`、`error`、`skipped`）时只返回该状态而不写库，保留上一次成功的
    榜单。

    Args:
        session: 异步数据库会话，由路由创建。
        direction: `agent` 或 `skill`，决定固定查询词。

    Returns:
        榜单响应；写入失败时回滚并返回 `error` 空榜单。

    Raises:
        ValueError: 方向不是 `agent` 或 `skill`。
    """
    if direction not in DIRECTION_QUERIES:
        raise ValueError(f"未知方向：{direction}")
    if not settings.last30days_enabled:
        return _empty_ranking(direction, "skipped", "last30days 模块已禁用。")

    async with _DIRECTION_LOCKS.setdefault(direction, asyncio.Lock()):
        result = await fetch_last30days(
            query=DIRECTION_QUERIES[direction], limit=_REFRESH_FETCH_LIMIT
        )
        status = str(result["status"])
        if status in {"unconfigured", "error", "skipped"}:
            response = _empty_ranking(direction, status, result.get("message") or "研究任务没有成功完成。")
            return response

        top_items = rank_items(result["items"], TOP_RANK_LIMIT)
        payload = {
            "items": top_items,
            "clusters": result["clusters"],
            "sources": result["sources"],
            "source_status": result["source_status"],
        }
        message = result.get("message")
        fetched_at = _parse_fetched_at(result.get("fetched_at"))
        try:
            await Last30DaysReportStore(session).upsert(
                direction=direction,
                status=status,
                payload=payload,
                message=message,
                fetched_at=fetched_at,
            )
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            return _empty_ranking(
                direction, "error", "榜单保存失败，请先执行最新的 schema.sql。"
            )
        return {
            "direction": direction,
            "status": status,
            "items": top_items,
            "clusters": result["clusters"],
            "sources": result["sources"],
            "source_status": result["source_status"],
            "fetched_at": fetched_at.replace(tzinfo=UTC).isoformat(),
            "message": message,
        }
