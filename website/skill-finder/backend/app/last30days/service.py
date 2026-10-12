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
    """Raised when the user-level last30days skill cannot be started."""


class Last30DaysExecutionError(RuntimeError):
    """Raised when the last30days engine fails or returns invalid output."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _skill_entrypoint() -> Path:
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
        "OPENAI_API_KEY",
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
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("status") or value.get("state") or "unknown")
    return "unknown"


async def fetch_last30days(query: str, limit: int = 50) -> dict[str, Any]:
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
    """Sort engine results by total engagement, descending, and keep the top `limit`."""
    valid = [item for item in items if isinstance(item, dict)]
    return sorted(
        valid, key=lambda item: _engagement_total(item.get("engagement")), reverse=True
    )[:limit]


def _empty_ranking(direction: str, status: str, message: str) -> dict[str, Any]:
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
