from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scrapling.fetchers import AsyncFetcher
from scrapling.parser import Selector

from app.collector.classifier import normalize_text

TRENDING_URL = "https://github.com/trending"
PERIODS: tuple[str, ...] = ("daily", "weekly", "monthly")
PERIOD_LABELS: dict[str, str] = {
    "daily": "today",
    "weekly": "this week",
    "monthly": "this month",
}

_NUMBER_PATTERN = re.compile(r"[\d,]+")
_STARS_PATTERN = re.compile(r"([\d,]+)\s*stars?\b", re.IGNORECASE)
_GAINED_PATTERN = re.compile(
    r"([\d,]+)\s+stars?\s+(today|this week|this month)", re.IGNORECASE
)


class TrendingScrapeError(Exception):
    """Raised when the GitHub trending page cannot be fetched or parsed."""


@dataclass(frozen=True)
class TrendingRepository:
    owner: str
    name: str
    full_name: str
    description: str | None
    language: str | None
    stars_total: int
    stars_gained: int
    rank: int


def parse_trending_html(html: str, period: str) -> list[TrendingRepository]:
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
    keywords = [keyword.strip().lower() for keyword in ai_keywords.split(",") if keyword.strip()]
    if not keywords:
        return None
    pattern = "|".join(rf"\b{re.escape(keyword)}\b" for keyword in keywords)
    return re.compile(pattern)


def is_ai_related(repository: TrendingRepository, matcher: re.Pattern[str] | None) -> bool:
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
    matcher = build_ai_matcher(ai_keywords)
    matched = [repo for repo in repositories if is_ai_related(repo, matcher)]
    matched.sort(key=lambda repo: (-repo.stars_gained, repo.rank))
    return matched[:top_n]


def _parse_gained(row: Any) -> int:
    gained_text = " ".join(row.css("span.float-sm-right::text").getall())
    if not gained_text.strip():
        gained_text = row.get_all_text()
    match = _GAINED_PATTERN.search(gained_text)
    if match:
        return _to_int(match.group(1))
    fallback = _STARS_PATTERN.search(gained_text)
    return _to_int(fallback.group(1)) if fallback else 0


def _parse_stars(text: str) -> int:
    match = _NUMBER_PATTERN.search(text)
    return _to_int(match.group(0)) if match else 0


def _to_int(value: str) -> int:
    return int(value.replace(",", "")) if value else 0


class TrendingScraper:
    """Fetches the three GitHub trending pages through Scrapling."""

    def __init__(self, proxy: str = "", timeout: float = 30.0) -> None:
        self._proxy = proxy.strip()
        self._timeout = timeout

    async def fetch(self, period: str) -> list[TrendingRepository]:
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
    body = getattr(page, "body", None)
    if isinstance(body, bytes):
        encoding = getattr(page, "encoding", None) or "utf-8"
        return body.decode(encoding, errors="replace")
    return str(page)
