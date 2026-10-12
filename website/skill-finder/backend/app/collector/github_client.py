from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

import httpx

GITHUB_API_BASE = "https://api.github.com"
ACCEPT_HEADER = "application/vnd.github+json"
RAW_ACCEPT_HEADER = "application/vnd.github.raw+json"
API_VERSION = "2022-11-28"
DEFAULT_RETRY_DELAYS = (0.5, 1.0, 2.0)
README_MAX_CHARS = 12000


@dataclass(frozen=True)
class GitHubRepository:
    github_id: int
    owner: str
    name: str
    full_name: str
    html_url: str
    homepage: str | None
    description: str | None
    language: str | None
    topics: list[str]
    stars_count: int
    forks_count: int
    open_issues_count: int
    archived: bool
    disabled: bool
    fork: bool
    github_created_at: datetime
    github_updated_at: datetime

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> GitHubRepository:
        return cls(
            github_id=int(payload["id"]),
            owner=payload["owner"]["login"],
            name=payload["name"],
            full_name=payload["full_name"],
            html_url=payload["html_url"],
            homepage=payload.get("homepage"),
            description=payload.get("description"),
            language=payload.get("language"),
            topics=list(payload.get("topics") or []),
            stars_count=int(payload.get("stargazers_count") or 0),
            forks_count=int(payload.get("forks_count") or 0),
            open_issues_count=int(payload.get("open_issues_count") or 0),
            archived=bool(payload.get("archived") or False),
            disabled=bool(payload.get("disabled") or False),
            fork=bool(payload.get("fork") or False),
            github_created_at=_parse_datetime(payload.get("created_at")),
            github_updated_at=_parse_datetime(payload.get("updated_at")),
        )


@dataclass(frozen=True)
class RateLimit:
    remaining: int
    reset_at: datetime


class GitHubError(Exception):
    pass


class GitHubAuthError(GitHubError):
    pass


class GitHubRateLimitError(GitHubError):
    def __init__(self, reset_at: datetime) -> None:
        self.reset_at = reset_at
        super().__init__("GitHub API rate limit exceeded")


class GitHubRequestError(GitHubError):
    pass


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if not value:
        return datetime.fromtimestamp(0, tz=UTC)
    if str(value).isdigit():
        return datetime.fromtimestamp(int(value), tz=UTC)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed


class GitHubClient:
    def __init__(
        self,
        token: str,
        retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
    ) -> None:
        self._token = token
        self._retry_delays = retry_delays
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(base_url=GITHUB_API_BASE, timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_repository(self, full_name: str) -> GitHubRepository | None:
        response = await self._request(
            "GET",
            f"/repos/{full_name}",
            status_codes=[200, 404],
        )
        if response.status_code == 404:
            return None
        return GitHubRepository.from_payload(response.json())

    async def get_readme(self, full_name: str) -> str | None:
        """Return the raw README text (truncated), or None when absent."""
        response = await self._request(
            "GET",
            f"/repos/{full_name}/readme",
            status_codes=[200, 404],
            accept=RAW_ACCEPT_HEADER,
        )
        if response.status_code == 404:
            return None
        text = response.text.strip()
        if not text:
            return None
        return text[:README_MAX_CHARS]

    async def get_rate_limit(self) -> RateLimit:
        response = await self._request("GET", "/rate_limit")
        resource = response.json()["resources"]["core"]
        reset_at = _parse_datetime(resource["reset"])
        return RateLimit(
            remaining=int(resource["remaining"]),
            reset_at=reset_at,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        status_codes: list[int] | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        assert self._client is not None
        allowed = status_codes or [200]
        last_exc: GitHubRequestError | None = None
        for attempt in range(len(self._retry_delays)):
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    headers={
                        "Accept": accept or ACCEPT_HEADER,
                        "Authorization": f"Bearer {self._token}",
                        "X-GitHub-Api-Version": API_VERSION,
                    },
                )
            except httpx.TransportError as exc:
                last_exc = GitHubRequestError(
                    f"GitHub transport failed: {type(exc).__name__}"
                )
                if attempt < len(self._retry_delays) - 1:
                    await asyncio.sleep(self._retry_delays[attempt])
                    continue
                raise last_exc from exc
            if response.status_code in allowed:
                return response
            if _is_rate_limited(response):
                raise GitHubRateLimitError(
                    _parse_datetime(response.headers.get("X-RateLimit-Reset"))
                )
            if response.status_code in (401, 403):
                raise GitHubAuthError(f"GitHub authentication failed: {response.status_code}")
            if response.status_code < 500:
                raise GitHubRequestError(f"GitHub request failed: {response.status_code}")
            last_exc = GitHubRequestError(f"GitHub server error: {response.status_code}")
            if attempt < len(self._retry_delays) - 1:
                await asyncio.sleep(self._retry_delays[attempt])
        raise last_exc or GitHubRequestError("GitHub request failed")


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
