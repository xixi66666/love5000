"""中文简介生成：先走统一模型，再回退到 service 原配置的模型链。

两级路由：

1. ``model_hub.try_chat``——若主页选了统一模型就用它，模型不可用会抛异常并被包成
   :class:`IntroductionAuthError`（认证类问题不重试）；
2. ``model.properties`` 的 ``service.skill-finder`` / ``intro.models`` 回退链——按顺序
   换模型，每个模型最多 ``_MAX_ATTEMPTS_PER_MODEL`` 次，只对 408/429/5xx/网络错误重试。

降级策略（:func:`generate_introductions_resilient`）：整批失败拆两半递归重试；单个仓库
仍失败则去掉 README 再试一次（内容审核有时会拒绝 README 正文），最终仍失败就留空，
让本轮采集降级成 ``PARTIAL`` 而不是整轮失败。

安全与凭据：密钥只来自 ``model.properties``，只放进请求头；异常文案、日志与返回值都
不含 Key、完整上游响应或私有路径。

会话所有权：接收 ``AsyncSession`` 的函数（:func:`_pending_ids_by_daily_growth`）只做只读
查询；:func:`run_introduction_backfill` 自己用 ``async_session_factory`` 开会话、写库并
在结束时 ``commit``，然后关闭。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, replace

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Repository, TrendingEntry
from app.db.session import async_session_factory
from app.repositories.repositories import RepositoryStore
from app.services import model_hub, model_settings

logger = logging.getLogger(__name__)

# 只对这些上游状态码重试：都是“过一会儿可能就好”的临时错误；401/400 之类的重试无意义。
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
# 同一个模型的最大尝试次数；配合指数退避（2**attempt 秒）使用，避免打爆上游。
_MAX_ATTEMPTS_PER_MODEL = 3


class IntroductionGenerationError(Exception):
    """模型没能产出可解析的简介。

    属于“可降级”的错误：调用方会拆批、去掉 README 重试，最终仍失败就留空并把采集标成
    ``PARTIAL``。文案只描述原因，不包含上游响应正文或密钥。
    """


class IntroductionAuthError(IntroductionGenerationError):
    """凭据不可用，换模型或拆分内容都不能修复。"""


class _UpstreamError(Exception):
    """可重试的网关故障（5xx、限流、无状态码的网络错误）。

    调用方在同一模型上按指数退避重试，重试耗尽后再换下一个模型。
    """


class _ModelRejected(Exception):
    """该模型无法完成这次请求（其他 4xx），换模型比重试更有效。

    调用方捕获后立即跳到回退链的下一个模型，不消耗重试次数。
    """


@dataclass
class RepositoryBrief:
    """送进模型的仓库材料。

    只挑模型真正用得上的字段（``to_payload`` 决定具体键），``readme`` 单独放在提示词的
    README 段落里，并可被剥掉后重试。
    """

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
        """转成提示词里“仓库信息”部分的字典。

        Returns:
            只含模型需要的键（owner/name/description/language/topics/stars/homepage），
            不含 README 与内部 id，减少提示词体积。
        """
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
    """拼一次性生成整批简介的提示词。

    结构：角色与字段说明 → 仓库元信息 JSON → README 段落（有才拼）→ 输出格式示例。
    提示词要求模型只输出 JSON 数组且顺序与输入一致，:func:`_parse_introductions` 依赖
    这个约定做按序对齐。

    Args:
        repos: 本批仓库摘要。

    Returns:
        完整提示词文本；没有任何 README 时不含 README 段落。
    """
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
    """把模型返回的列表字段收敛成去空白的字符串列表。

    模型偶尔把数字或 ``None`` 塞进数组，这里只接受字符串与整数，其余丢弃，避免把
    脏值写进 ``repositories.introduction``。

    Args:
        values: 任意值；不是列表时返回空列表。

    Returns:
        去空白后的字符串列表。
    """
    if not isinstance(values, list):
        return []
    return [
        str(value).strip()
        for value in values
        if isinstance(value, (str, int)) and str(value).strip()
    ]


def _parse_introductions(text: str, count: int) -> list[str]:
    """从模型输出里截出 JSON 数组并归一成简介 JSON 文本。

    模型常在数组外多写解释或 Markdown 围栏，因此用正则抓第一个 ``[...]`` 再解析；
    元素可以是对象也可以是纯字符串（旧提示词格式），都经 :func:`_introduction_payload`
    统一成六个字段的结构。

    Args:
        text: 模型返回的原始内容。
        count: 期望条数，必须与输入仓库数一致，少于它视为失败。

    Returns:
        长度为 ``count`` 的 JSON 字符串列表，直接可写入 ``repositories.introduction``。

    Raises:
        IntroductionGenerationError: 找不到数组、JSON 非法、条数不足，或某个元素既不是
            对象也不是字符串。
    """
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
    """把单个模型元素归一成六字段简介结构。

    Args:
        entry: 模型返回的对象，或旧格式的纯文本简介。

    Returns:
        ``introduction`` / ``highlights`` / ``requirements`` / ``usage`` /
        ``audience`` / ``domains`` 六个键的字典；缺失字段用空值兜底。
    """
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
    """构造只有正文、其余字段为空的简介结构。

    Args:
        introduction: 简介正文，可为空串。

    Returns:
        六字段齐全的字典，供前端统一取值而不用判空。
    """
    return {
        "introduction": introduction,
        "highlights": [],
        "requirements": [],
        "usage": "",
        "audience": "",
        "domains": [],
    }


def _model_chain(raw: str) -> list[str]:
    """把逗号分隔的模型串拆成网关 API 模型名。

    ``provider/model`` 形式只保留斜杠后的模型名（网关自己知道 provider），并按首次出现
    顺序去重，保证回退链不会重复尝试同一个模型。

    Args:
        raw: 例如 ``"deepseek/deepseek-chat,deepseek-reasoner"``。

    Returns:
        去重后的模型名列表；输入为空时返回空列表。
    """
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
    """取简介模型的 API Key。

    Returns:
        ``model.properties`` 里的 intro key。

    Raises:
        IntroductionAuthError: 未配置 Key。换模型、拆批都不会让它变好，因此直接停止。
            消息只说明“未配置”，不回显任何配置内容。
    """
    key = model_settings.intro_api_key()
    if not key:
        raise IntroductionAuthError("model.properties 的 intro.api-key 未配置。")
    return key


async def _call_chat(
    client: httpx.AsyncClient, base_url: str, api_model: str, api_key: str, prompt: str, timeout: float
) -> str:
    """用显式地址与密钥调用一次 OpenAI 兼容的 ``/chat/completions``。

    请求头带固定 User-Agent 与随机 ``x-opencode-session``（网关侧据此区分会话）。
    上游错误按可恢复性分类：401 归为认证失败（不可重试），无状态码或
    ``_RETRYABLE_STATUS`` 归为可重试，其余状态码说明该模型不可用，换下一个模型。

    Args:
        client: 复用的 httpx 异步客户端（整条回退链共用一个连接池）。
        base_url: 基础地址，不含 ``/chat/completions``。
        api_model: 网关侧模型名。
        api_key: 请求头里的密钥，不写日志。
        prompt: 完整提示词。
        timeout: 单次请求超时秒数。

    Returns:
        模型返回的正文文本（可能是带围栏的 JSON 数组）。

    Raises:
        IntroductionAuthError: 上游 401。
        _UpstreamError: 可重试错误（限流、5xx、网络异常）或返回内容为空。
        _ModelRejected: 该模型对该请求不可用（其他 4xx），调用方应换模型。
    """
    try:
        data = await model_hub.native_chat(
            client,
            f"{base_url}/chat/completions",
            api_key,
            {"model": api_model, "messages": [{"role": "user", "content": prompt}]},
            headers={
                "User-Agent": "skill-finder/1.0",
                "x-opencode-session": uuid.uuid4().hex,
            },
            timeout=timeout,
        )
    except model_hub.ModelProviderError as exc:
        if exc.status == 401:
            raise IntroductionAuthError("简介服务认证失败或密钥已过期，请更新私有配置中的密钥。") from None
        if exc.status is None or exc.status in _RETRYABLE_STATUS:
            raise _UpstreamError(f"{api_model}: 模型暂时不可用") from None
        raise _ModelRejected(f"{api_model}: HTTP {exc.status}") from None
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
    """生成一批中文简介，失败时按模型回退链重试。

    先尝试统一模型（主页选择），拿不到就退回 ``model.properties`` 配置的模型链；
    认证失败**不会**降级到下一个模型，因为换 Key 才有用。

    Args:
        repos: 本批仓库摘要，为空时直接返回空列表。
        model: 显式指定的模型串（逗号分隔），为空则读配置。
        timeout: 单次请求超时秒数，缺省取 ``settings.intro_timeout_seconds``。

    Returns:
        与 ``repos`` 等长、顺序一致的简介 JSON 文本列表。

    Raises:
        IntroductionAuthError: 统一模型调用抛错，或 ``model.properties`` 的 Key 缺失。
        IntroductionGenerationError: 所有模型都失败，或没有可用模型配置。
    """
    if not repos:
        return []
    prompt = _build_prompt(repos)
    try:
        response = await model_hub.try_chat({
            "messages": [{"role": "user", "content": prompt}],
        })
        if response is not None:
            text = (response.get("choices") or [{}])[0].get("message", {}).get("content", "")
            return _parse_introductions(text, len(repos))
    except Exception as exc:
        # 延续认证失败即停止的语义，不拆分、不换模型重试。
        raise IntroductionAuthError("统一模型请求失败，请检查已选模型后重试。") from exc
    chain = model_settings.intro_models(model or "")
    if not chain:
        raise IntroductionGenerationError("model.properties 未配置 service.skill-finder 或 intro.models。")
    api_key = _resolve_api_key()
    base_url = model_settings.intro_base_url()
    seconds = timeout or settings.intro_timeout_seconds
    last_error: Exception | None = None
    async with httpx.AsyncClient() as client:
        for api_model in chain:
            for attempt in range(_MAX_ATTEMPTS_PER_MODEL):
                try:
                    text = await _call_chat(client, base_url, api_model, api_key, prompt, seconds)
                    return _parse_introductions(text, len(repos))
                except IntroductionAuthError:
                    raise
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
    """生成简介，整批失败时逐级降级。

    失败的一批会拆成两半递归重试；单个仓库仍然失败时去掉 README 再试一次
    （内容审核有时会拒绝 README 正文），最终仍失败就留 ``None``。

    Args:
        briefs: 待生成简介的仓库摘要。

    Returns:
        与 ``briefs`` 等长的列表；某项最终失败时该位置为 ``None``，由调用方计入缺失。

    Raises:
        IntroductionAuthError: 凭据问题与仓库内容无关，不拆分、不去 README，直接上抛，
            让调用方停止本轮剩余批次。
    """
    if not briefs:
        return []
    try:
        return list(await generate_introductions(briefs))
    except IntroductionAuthError:
        # 认证错误与仓库内容无关，不拆分重试，不把上游响应正文写入日志。
        raise
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
        except IntroductionAuthError:
            raise
        except IntroductionGenerationError as exc:
            logger.warning(
                "introduction without README failed for %s/%s: %s",
                brief.owner,
                brief.name,
                exc,
            )
    return [None]


def brief_from_repository(repository, readme: str | None = None) -> RepositoryBrief:
    """把 ORM 仓库对象转成模型输入。

    Args:
        repository: ``Repository`` ORM 对象（不在这里触发额外查询）。
        readme: 已抓到的 README 原文，可为 ``None``。

    Returns:
        :class:`RepositoryBrief`。
    """
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
    """尽量为每个仓库取 README，失败则退化为 ``None``。

    单个仓库失败（404、限流、网络错误）只记日志并填 ``None``；连客户端都建不起来时
    整批填 ``None``，让简介退化为只依据元信息生成，而不是让补全任务整体失败。

    Args:
        repos: 仓库 ORM 对象列表。

    Returns:
        与入参等长的列表，元素为 README 文本或 ``None``。
    """
    from app.collector.github_client import GitHubClient, GitHubError

    token = settings.github_token.get_secret_value()
    readmes: list[str | None] = []
    try:
        async with GitHubClient(token=token, proxy=settings.trending_proxy) as client:
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
    """按当日增量挑出缺简介的仓库主键。

    左连接日榜，``daily_stars IS NULL`` 排在后面（先补当天有热度的项目），再用总 Star 与
    id 兜底稳定顺序，保证多次补全不会反复挑同一批。

    Args:
        session: 调用方打开的只读会话（本函数不提交，事务由 ``run_introduction_backfill``
            统一提交）。
        limit: 最多返回多少个主键。

    Returns:
        ``repositories.id`` 列表，按优先级降序。
    """
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
    """为缺简介的仓库补全介绍（后台任务，由管理接口触发）。

    自己用 ``async_session_factory`` 打开会话并在结束时 ``commit``，因此可以被
    ``BackgroundTasks`` 直接调用，不依赖请求的会话；已存在的简介不会被覆盖（筛选条件就是
    ``introduction IS NULL``）。批次并发由 ``settings.intro_concurrency`` 限制，避免同时
    打开过多上游请求。

    Args:
        category: 只补某个分类，``None`` 表示不限。
        limit: 本次最多处理多少个仓库。
        order: 传 ``daily`` 时按当日增量优先，其余按总 Star。

    Returns:
        ``{"updated": 成功数, "failed": 失败数, "total": 本次候选数}``。
    """
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
            """取 README、生成简介，返回该批次与结果（结果可能含 ``None``）。

            并发受外层信号量限制；本函数不吞异常之外的错误，鉴权失败会向上冒泡终止
            整个补全任务。
            """
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
