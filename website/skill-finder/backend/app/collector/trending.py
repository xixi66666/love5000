"""抓取并解析 GitHub Trending 日/周/月榜。

抓取走 Scrapling 的 ``AsyncFetcher``（``stealthy_headers`` + 重试，可挂代理），
解析用 CSS 选择器读取 ``article.Box-row``。页面是公开 HTML 而非 API，结构一旦调整
解析就会取空，因此 ``TrendingScraper.fetch`` 把“零结果”也当成错误抛出，
避免把空榜单当成真实数据落库。

失败统一抛 :class:`TrendingScrapeError`（消息只带周期名与异常类型），
由 :class:`app.collector.service.CollectionService` 决定是降级为 ``PARTIAL`` 还是整轮失败。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scrapling.fetchers import AsyncFetcher
from scrapling.parser import Selector

from app.collector.classifier import normalize_text

# 榜单页地址与三个周期；周期值同时用于 `?since=` 查询参数与 period 列取值。
TRENDING_URL = "https://github.com/trending"
PERIODS: tuple[str, ...] = ("daily", "weekly", "monthly")
# 页面文案里的周期短语；解析到的 "stars today/this week/this month" 依赖它们。
PERIOD_LABELS: dict[str, str] = {
    "daily": "today",
    "weekly": "this week",
    "monthly": "this month",
}

# 解析用正则：纯数字（含千分位逗号）、总 Star 文案、"N stars today/this week" 增量文案。
_NUMBER_PATTERN = re.compile(r"[\d,]+")
_STARS_PATTERN = re.compile(r"([\d,]+)\s*stars?\b", re.IGNORECASE)
_GAINED_PATTERN = re.compile(
    r"([\d,]+)\s+stars?\s+(today|this week|this month)", re.IGNORECASE
)


class TrendingScrapeError(Exception):
    """抓取或解析 GitHub Trending 页面失败。

    消息只带周期名与异常类型（不含页面内容），由采集服务决定是把本轮标成
    ``PARTIAL`` 还是 ``FAILED``。
    """


@dataclass(frozen=True)
class TrendingRepository:
    """榜单页上的一行。

    Attributes:
        owner: 仓库所有者（取自 ``h2 a`` 的 href 第一段）。
        name: 仓库名（href 第二段）。
        full_name: ``owner/name``，也是后续 GitHub API 补全的主键。
        description: 页面上的描述，可能缺失。
        language: 页面标注的主要语言，可能缺失。
        stars_total: 页面显示的总 Star 数，解析失败按 0 处理。
        stars_gained: 周期内新增 Star，用于排序与展示。
        rank: 页面原始名次（1 开始），用于增量并列时的稳定排序。
    """

    owner: str
    name: str
    full_name: str
    description: str | None
    language: str | None
    stars_total: int
    stars_gained: int
    rank: int


def parse_trending_html(html: str, period: str) -> list[TrendingRepository]:
    """把 Trending 页面 HTML 解析成仓库列表。

    逐行读取 ``article.Box-row``：href 不足两段的行（广告、组织卡片）直接跳过，
    其余字段缺失时按 ``None`` / 0 兜底，保证单行结构异常不会打断整页解析。

    Args:
        html: 页面 HTML 文本。
        period: ``daily`` / ``weekly`` / ``monthly``，仅用于校验入参。

    Returns:
        按页面顺序排列的仓库列表；页面结构变化时可能为空列表，由调用方判空。

    Raises:
        ValueError: ``period`` 不是已知周期。
    """
    if period not in PERIODS:
        raise ValueError(f"unknown trending period: {period}")

    page = Selector(html)
    repositories: list[TrendingRepository] = []
    for rank, row in enumerate(page.css("article.Box-row"), start=1):
        href = (row.css("h2 a::attr(href)").get() or "").strip()
        parts = [segment for segment in href.split("/") if segment]
        if len(parts) < 2:
            continue
        owner, name = parts[0], parts[1]

        description = row.css("p::text").get()
        language = row.css('[itemprop="programmingLanguage"]::text').get()

        repositories.append(
            TrendingRepository(
                owner=owner,
                name=name,
                full_name=f"{owner}/{name}",
                description=description.strip() if description else None,
                language=language.strip() if language else None,
                stars_total=_parse_stars(
                    " ".join(row.css('a[href$="/stargazers"]::text').getall())
                ),
                stars_gained=_parse_gained(row),
                rank=rank,
            )
        )
    return repositories


def build_ai_matcher(ai_keywords: str) -> re.Pattern[str] | None:
    """把逗号分隔的 AI 关键词编译成一个词边界正则。

    Args:
        ai_keywords: 逗号分隔的关键词串（大小写不敏感，空项会被忽略）。

    Returns:
        合并后的正则；关键词为空时返回 ``None``，表示“不做过滤、全部保留”，
        便于本地临时关闭 AI 过滤而不改代码。
    """
    keywords = [keyword.strip().lower() for keyword in ai_keywords.split(",") if keyword.strip()]
    if not keywords:
        return None
    pattern = "|".join(rf"\b{re.escape(keyword)}\b" for keyword in keywords)
    return re.compile(pattern)


def is_ai_related(repository: TrendingRepository, matcher: re.Pattern[str] | None) -> bool:
    """判断仓库名称或描述是否命中 AI 关键词。

    文本先经 :func:`normalize_text` 归一（驼峰拆分 + 非字母数字折叠），因此
    ``LLM`` 与 ``llm-agent`` 都能与关键词的正则边界匹配。

    Args:
        repository: 榜单行。
        matcher: :func:`build_ai_matcher` 的产物，``None`` 时恒为 ``True``。

    Returns:
        是否与 AI 相关。
    """
    if matcher is None:
        return True
    fields = " ".join(
        normalize_text(value)
        for value in (repository.name, repository.description or "")
        if value
    )
    return matcher.search(fields) is not None


def select_trending(
    repositories: list[TrendingRepository], ai_keywords: str, top_n: int
) -> list[TrendingRepository]:
    """过滤出 AI 相关仓库并取增量最高的前 N 个。

    排序键为 ``(-stars_gained, rank)``：增量相同时按页面原始名次，保证结果可复现。
    过滤后可能不足 ``top_n`` 个，不会补位，也不会把非 AI 仓库塞进榜单。

    Args:
        repositories: 已解析的整页榜单。
        ai_keywords: 逗号分隔关键词，空串表示不过滤。
        top_n: 每个周期保留的条数。

    Returns:
        排序后的子列表，可能为空。
    """
    matcher = build_ai_matcher(ai_keywords)
    matched = [repo for repo in repositories if is_ai_related(repo, matcher)]
    matched.sort(key=lambda repo: (-repo.stars_gained, repo.rank))
    return matched[:top_n]


def _parse_gained(row: Any) -> int:
    """从榜单行里解析周期增量 Star。

    优先读右上角的 ``span.float-sm-right``；该节点缺失（页面结构变化）时退化为扫描
    整行文本。先匹配“N stars today/this week/this month”，再退化为任意“N stars”，
    都失败则返回 0，绝不因为一段文案异常让整页解析失败。

    Args:
        row: Scrapling 的 ``article.Box-row`` 选择器。

    Returns:
        解析到的增量；无法解析时为 0。
    """
    gained_text = " ".join(row.css("span.float-sm-right::text").getall())
    if not gained_text.strip():
        gained_text = row.get_all_text()
    match = _GAINED_PATTERN.search(gained_text)
    if match:
        return _to_int(match.group(1))
    fallback = _STARS_PATTERN.search(gained_text)
    return _to_int(fallback.group(1)) if fallback else 0


def _parse_stars(text: str) -> int:
    """从文本里取出第一个带千分位的数字。

    Args:
        text: 例如 ``"1,234"`` 或空串。

    Returns:
        Star 总数；没有数字时为 0。
    """
    match = _NUMBER_PATTERN.search(text)
    return _to_int(match.group(0)) if match else 0


def _to_int(value: str) -> int:
    """去掉千分位逗号后转整数。

    Args:
        value: 形如 ``"12,345"`` 的文本，可为空串。

    Returns:
        整数值；空串按 0 处理。
    """
    return int(value.replace(",", "")) if value else 0


class TrendingScraper:
    """通过 Scrapling 拉取三个 Trending 页面。

    每次 :meth:`fetch` 都是一个独立请求，不缓存页面：榜单本身就是“当前快照”，
    缓存反而会写错时间点。代理与超时在构造时固定，便于测试注入假值。
    """

    def __init__(self, proxy: str = "", timeout: float = 30.0) -> None:
        self._proxy = proxy.strip()
        self._timeout = timeout

    async def fetch(self, period: str) -> list[TrendingRepository]:
        """抓取并解析一个周期的榜单。

        Args:
            period: ``daily`` / ``weekly`` / ``monthly``。

        Returns:
            该周期的仓库列表，按页面顺序。

        Raises:
            ValueError: 周期未知（属于调用方编程错误，WIP 时不重试）。
            TrendingScrapeError: 网络/代理失败、状态码非 200、解析结果为空
                （页面结构可能已变化）。消息只带周期名与异常类型，便于降级判断。
        """
        if period not in PERIODS:
            raise ValueError(f"unknown trending period: {period}")

        kwargs: dict[str, Any] = {
            "stealthy_headers": True,
            "timeout": self._timeout,
            "retries": 2,
            "retry_delay": 1,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy

        try:
            page = await AsyncFetcher.get(f"{TRENDING_URL}?since={period}", **kwargs)
        except Exception as exc:
            raise TrendingScrapeError(
                f"fetch trending {period} failed: {type(exc).__name__}"
            ) from exc

        if page.status != 200:
            raise TrendingScrapeError(f"trending {period} returned HTTP {page.status}")

        html = _response_html(page)
        repositories = parse_trending_html(html, period)
        if not repositories:
            raise TrendingScrapeError(
                f"trending {period} page yielded no repositories; markup may have changed"
            )
        return repositories


def _response_html(page: Any) -> str:
    """取出响应正文并按响应自带的编码解码。

    Scrapling 在不同版本里可能返回 bytes 或可直接 ``str()`` 的对象；
    未知编码时按 utf-8 容错解码，不抛 UnicodeDecodeError。

    Args:
        page: Scrapling 的响应对象。

    Returns:
        HTML 文本。
    """
    body = getattr(page, "body", None)
    if isinstance(body, bytes):
        encoding = getattr(page, "encoding", None) or "utf-8"
        return body.decode(encoding, errors="replace")
    return str(page)
