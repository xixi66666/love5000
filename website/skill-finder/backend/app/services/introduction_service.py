from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Repository, TrendingEntry
from app.db.session import async_session_factory
from app.repositories.repositories import RepositoryStore

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS_PER_MODEL = 3


class IntroductionGenerationError(Exception):
    """Raised when the model gateway cannot produce an introduction."""


class _UpstreamError(Exception):
    """Retryable gateway failure (5xx, rate limit, network)."""


class _ModelRejected(Exception):
    """Non-retryable failure for this model; fall through to the next one."""


@dataclass
class RepositoryBrief:
    owner: str
    name: str
    description: str | None
    language: str | None
    topics: list[str]
    stars_count: int
    homepage: str | None
    html_url: str
    readme: str | None = None

    def to_payload(self) -> dict:
        return {
            "owner": self.owner,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "topics": self.topics,
            "stars": self.stars_count,
            "homepage": self.homepage,
        }


def _build_prompt(repos: list[RepositoryBrief]) -> str:
    payload = json.dumps([r.to_payload() for r in repos], ensure_ascii=False, indent=2)
    readme_blocks = "\n\n".join(
        f"### {repo.owner}/{repo.name} 的 README\n{repo.readme}"
        for repo in repos
        if repo.readme
    )
    readme_section = f"README 原文：\n{readme_blocks}\n\n" if readme_blocks else ""
    return (
        "你是开源项目中文介绍撰写助手。请根据每个仓库的元信息和 README 原文，"
        "为每个仓库写一份详细的中文介绍。输出 JSON 数组，顺序与输入完全一致，"
        "每个元素包含以下字段：\n"
        "1. introduction：4-6 句中文，说明这个项目是什么、解决什么问题、核心思路和主要特点；\n"
        "2. highlights：3-6 条核心功能或亮点，每条一句话；\n"
        "3. requirements：运行或安装所需的前置条件（语言版本、工具、依赖），没有就输出空数组；\n"
        "4. usage：如何使用或快速开始，3-6 句，README 里有具体命令就原样保留命令；\n"
        "5. audience：适合什么人使用，1-2 句；\n"
        "6. domains：3-5 个领域名词短语，例如 AI Agent、RAG、自动化、前端开发。\n"
        "只能基于提供的材料撰写，不要编造事实，不要输出任何解释或前缀。"
        "不要使用任何工具，不要读取或搜索任何文件，直接回答。\n\n"
        f"仓库信息：\n{payload}\n\n"
        f"{readme_section}"
        "输出要求：只输出一个 JSON 数组，例如：\n"
        '[{"introduction": "项目介绍", "highlights": ["亮点一"], '
        '"requirements": ["Node.js 22+"], "usage": "安装和使用步骤", '
        '"audience": "适合人群", "domains": ["领域一", "领域二"]}]'
    )


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        str(value).strip()
        for value in values
        if isinstance(value, (str, int)) and str(value).strip()
    ]


def _parse_introductions(text: str, count: int) -> list[str]:
    """Extract a JSON array of rich introduction objects."""
    text = text.strip()
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        raise IntroductionGenerationError("could not parse introductions from model output")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise IntroductionGenerationError(
            "could not parse introductions from model output"
        ) from exc
    if not isinstance(parsed, list) or len(parsed) < count:
        raise IntroductionGenerationError("could not parse introductions from model output")
    items: list[str] = []
    for entry in parsed[:count]:
        if isinstance(entry, str):
            items.append(json.dumps(_introduction_payload(entry), ensure_ascii=False))
            continue
        if not isinstance(entry, dict):
            raise IntroductionGenerationError(
                "could not parse introductions from model output"
            )
        items.append(json.dumps(_introduction_payload(entry), ensure_ascii=False))
    return items


def _introduction_payload(entry: dict | str) -> dict:
    if isinstance(entry, str):
        return _empty_introduction(introduction=entry.strip())
    return {
        "introduction": str(entry.get("introduction", "")).strip(),
        "highlights": _string_list(entry.get("highlights")),
        "requirements": _string_list(entry.get("requirements")),
        "usage": str(entry.get("usage", "")).strip(),
        "audience": str(entry.get("audience", "")).strip(),
        "domains": _string_list(entry.get("domains")),
    }


def _empty_introduction(introduction: str = "") -> dict:
    return {
        "introduction": introduction,
        "highlights": [],
        "requirements": [],
        "usage": "",
        "audience": "",
        "domains": [],
    }


def _model_chain(raw: str) -> list[str]:
    """Split a comma-separated model list into gateway API model names."""
    chain: list[str] = []
    for part in raw.split(","):
        model = part.strip()
        if not model:
            continue
        api_model = model.split("/", 1)[1] if "/" in model else model
        if api_model not in chain:
            chain.append(api_model)
    return chain


def _resolve_api_key() -> str:
    if settings.opencode_api_key.strip():
        return settings.opencode_api_key.strip()
    auth_path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
        key = str((data.get("opencode-go") or {}).get("key") or "")
    except (OSError, json.JSONDecodeError):
        key = ""
    if not key:
        raise IntroductionGenerationError(
            "未找到模型网关密钥：请设置 OPENCODE_API_KEY，或先在本机 opencode 登录。"
        )
    return key


async def _call_chat(
    client: httpx.AsyncClient, api_model: str, api_key: str, prompt: str, timeout: float
) -> str:
    response = await client.post(
        f"{settings.intro_api_base}/chat/completions",
        json={"model": api_model, "messages": [{"role": "user", "content": prompt}]},
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "skill-finder/1.0",
            "x-opencode-session": uuid.uuid4().hex,
        },
        timeout=timeout,
    )
    if response.status_code in _RETRYABLE_STATUS:
        raise _UpstreamError(f"{api_model}: HTTP {response.status_code}")
    if response.status_code >= 400:
        detail = response.text[:300].replace("\n", " ")
        raise _ModelRejected(f"{api_model}: HTTP {response.status_code} {detail}")
    try:
        data = response.json()
    except ValueError as exc:
        raise _UpstreamError(f"{api_model}: invalid JSON response") from exc
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise _UpstreamError(f"{api_model}: empty content")
    return content


async def generate_introductions(
    repos: list[RepositoryBrief],
    *,
    model: str | None = None,
    timeout: int | None = None,
) -> list[str]:
    """Generate Chinese introductions via the model gateway, with a fallback chain."""
    if not repos:
        return []
    chain = _model_chain(model or settings.intro_model)
    if not chain:
        raise IntroductionGenerationError("INTRO_MODEL 未配置任何可用模型。")
    api_key = _resolve_api_key()
    prompt = _build_prompt(repos)
    seconds = timeout or settings.intro_timeout_seconds
    last_error: Exception | None = None
    async with httpx.AsyncClient() as client:
        for api_model in chain:
            for attempt in range(_MAX_ATTEMPTS_PER_MODEL):
                try:
                    text = await _call_chat(client, api_model, api_key, prompt, seconds)
                    return _parse_introductions(text, len(repos))
                except _ModelRejected as exc:
                    last_error = exc
                    break
                except (_UpstreamError, IntroductionGenerationError, httpx.HTTPError) as exc:
                    last_error = exc
                    await asyncio.sleep(2**attempt)
    raise IntroductionGenerationError(str(last_error) or "所有简介模型都失败了。")


async def generate_introductions_resilient(
    briefs: list[RepositoryBrief],
) -> list[str | None]:
    """Generate introductions, degrading gracefully when a batch fails.

    A failed batch is retried as two halves; a single repository that still
    fails is retried once without its README (content moderation sometimes
    rejects README text) and finally left as None.
    """
    if not briefs:
        return []
    try:
        return list(await generate_introductions(briefs))
    except IntroductionGenerationError as exc:
        logger.warning("introduction batch (%d) failed: %s", len(briefs), exc)

    if len(briefs) > 1:
        middle = len(briefs) // 2
        left = await generate_introductions_resilient(briefs[:middle])
        right = await generate_introductions_resilient(briefs[middle:])
        return left + right

    brief = briefs[0]
    if brief.readme:
        try:
            texts = await generate_introductions([replace(brief, readme=None)])
            logger.info(
                "introduction for %s/%s succeeded without README",
                brief.owner,
                brief.name,
            )
            return list(texts)
        except IntroductionGenerationError as exc:
            logger.warning(
                "introduction without README failed for %s/%s: %s",
                brief.owner,
                brief.name,
                exc,
            )
    return [None]


def brief_from_repository(repository, readme: str | None = None) -> RepositoryBrief:
    return RepositoryBrief(
        owner=repository.owner,
        name=repository.name,
        description=repository.description,
        language=repository.language,
        topics=list(repository.topics or []),
        stars_count=repository.stars_count,
        homepage=repository.homepage,
        html_url=repository.html_url,
        readme=readme,
    )


async def fetch_readmes(repos: list[Repository]) -> list[str | None]:
    """Best-effort README fetch for introduction generation."""
    from app.collector.github_client import GitHubClient, GitHubError

    token = settings.github_token.get_secret_value()
    readmes: list[str | None] = []
    try:
        async with GitHubClient(token=token) as client:
            for repo in repos:
                try:
                    readmes.append(await client.get_readme(repo.full_name))
                except GitHubError as exc:
                    logger.warning("readme fetch failed for %s: %s", repo.full_name, exc)
                    readmes.append(None)
    except GitHubError as exc:
        logger.warning("readme client unavailable: %s", exc)
        readmes = [None] * len(repos)
    return readmes


async def _pending_ids_by_daily_growth(session: AsyncSession, limit: int) -> list[int]:
    """Repository ids missing an introduction, ordered by today's trending star gain."""
    daily = (
        select(
            TrendingEntry.repository_id.label("repository_id"),
            TrendingEntry.stars_gained.label("daily_stars"),
        )
        .where(TrendingEntry.period == "daily")
        .subquery()
    )
    query = (
        select(Repository.id)
        .outerjoin(daily, Repository.id == daily.c.repository_id)
        .where(Repository.available.is_(True), Repository.introduction.is_(None))
        .order_by(
            daily.c.daily_stars.is_(None),
            daily.c.daily_stars.desc(),
            Repository.stars_count.desc(),
            Repository.id.desc(),
        )
        .limit(limit)
    )
    rows = await session.execute(query)
    return [row[0] for row in rows.all()]


async def run_introduction_backfill(
    *,
    category: str | None = None,
    limit: int = 5,
    order: str | None = None,
) -> dict:
    """Generate introductions for repositories missing one, in the background."""
    async with async_session_factory() as session:
        store = RepositoryStore(session)
        if order == "daily":
            ids = await _pending_ids_by_daily_growth(session, limit)
            pending = await store.list_by_ids(ids)
        else:
            pending = await store.list_without_introduction(category=category, limit=limit)

        updated = 0
        failed = 0
        batch_size = settings.intro_batch_size
        batches = [
            pending[start : start + batch_size]
            for start in range(0, len(pending), batch_size)
        ]
        semaphore = asyncio.Semaphore(max(1, settings.intro_concurrency))

        async def run_batch(batch: list[Repository]):
            async with semaphore:
                readmes = await fetch_readmes(batch)
                briefs = [
                    brief_from_repository(repo, readme=readme)
                    for repo, readme in zip(batch, readmes)
                ]
                texts = await generate_introductions_resilient(briefs)
                return batch, texts

        for batch, texts in await asyncio.gather(*(run_batch(b) for b in batches)):
            if texts is None:
                failed += len(batch)
                continue
            for repo, text in zip(batch, texts):
                if not text:
                    failed += 1
                    continue
                await store.update_introduction(repo.github_id, text)
                updated += 1
        await session.commit()
    return {"updated": updated, "failed": failed, "total": len(pending)}
