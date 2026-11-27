"""GitHub REST API 的最小异步客户端（仅采集需要的几个端点）。

只实现仓库元信息、README、限流查询三个调用，全部走 ``httpx.AsyncClient``，
可挂 ``TRENDING_PROXY`` 指定的代理。错误按可恢复性分层：

- 传输层异常与 5xx 按 ``DEFAULT_RETRY_DELAYS`` 指数退避重试；
- 403 且剩余额度为 0 判定为限流，抛 :class:`GitHubRateLimitError`（带重置时间）；
- 401/403 抛 :class:`GitHubAuthError`，说明换重试没有意义；
- 其余 4xx 抛 :class:`GitHubRequestError`，由调用方决定跳过这个仓库。

Token 只存在实例字段里并作为请求头下发，异常消息只带状态码与异常类型，
不会把 Authorization 内容写进日志。
"""
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
# 重试退避秒数；同时决定总尝试次数（len(DEFAULT_RETRY_DELAYS) 次）。
DEFAULT_RETRY_DELAYS = (0.5, 1.0, 2.0)
# README 截断长度：足够模型理解项目，又不至于把单次请求撑到几十 KB。
README_MAX_CHARS = 12000


@dataclass(frozen=True)
class GitHubRepository:
    """``/repos/{full_name}`` 归一后的仓库快照。

    字段与 ``repositories`` 表一一对应；``archived`` / ``disabled`` / ``fork`` 由
    :meth:`app.collector.service.CollectionService._eligible` 使用，用来过滤
    不再维护或非原创的仓库。
    """

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
        """把 GitHub 原始 JSON 转成数据类。

        ``stargazers_count`` / ``forks_count`` 等字段允许缺失（部分端点在无权限时
        省略），统一兜底为 0；``topics`` 缺失时为空列表。

        Args:
            payload: ``GET /repos/{full_name}`` 的响应体。

        Returns:
            归一后的 :class:`GitHubRepository`；时间字段经 :func:`_parse_datetime`
            解析为带时区的 datetime。
        """
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
    """GitHub 核心额度快照。

    Attributes:
        remaining: 剩余请求数。
        reset_at: 额度重置时间（UTC），写入 ``collection_runs.rate_limit_reset_at``，
            供排查“采集为什么停了”时对照。
    """

    remaining: int
    reset_at: datetime


class GitHubError(Exception):
    """所有 GitHub 调用错误的基类，便于调用方一次性兜住。"""

    pass  # noqa: PIE790


class GitHubAuthError(GitHubError):
    """Token 缺失、过期或无权限（401/403）。重试与换代理都无法修复，采集应尽快失败。"""

    pass  # noqa: PIE790


class GitHubRateLimitError(GitHubError):
    """请求额度耗尽。

    ``reset_at`` 来自响应头 ``X-RateLimit-Reset``，用于让本轮采集把重置时间写进
    ``collection_runs``，而不是盲目重试继续消耗额度。
    """

    def __init__(self, reset_at: datetime) -> None:
        self.reset_at = reset_at
        super().__init__("GitHub API rate limit exceeded")


class GitHubRequestError(GitHubError):
    """单个仓库请求失败（4xx、5xx 重试后仍失败或传输异常）。

    采集服务捕获它后只把这一个仓库计入 ``failed_count`` 并继续处理其他仓库，
    因此它代表“可跳过的局部失败”，不是整体采集中断。
    """

    pass  # noqa: PIE790


def _parse_datetime(value: Any) -> datetime:
    """把 GitHub 返回的时间字段解析成带时区的 datetime。

    兼容三种形态：已经是 datetime（测试替身会直接传）、Unix 时间戳（限流接口的
    ``reset`` 是秒数）、ISO 8601 字符串。缺失值返回 Unix 纪元，保证
    ``repositories.github_created_at`` 这类非空列不会写失败。

    Args:
        value: 原始时间值。

    Returns:
        带时区的 datetime；字符串无时区时按原样保留，由上层决定如何比较。
    """
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
    """GitHub API 异步客户端，必须用 ``async with`` 管理生命周期。

    进入上下文时创建 ``httpx.AsyncClient``，退出时关闭；底层连接池不复用，
    因为一次采集就是一批短请求，调用方（采集编排或 README 补全）各自持有实例。
    """

    def __init__(
        self,
        token: str,
        retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
        proxy: str = "",
    ) -> None:
        """保存凭据与传输参数，此时还不建立连接。

        Args:
            token: GitHub Token，可为空串（匿名调用额度很低，采集仍可跑但更容易限流）。
            retry_delays: 每次重试前等待的秒数序列，测试可传空元组关闭重试。
            proxy: 代理地址，空串表示直连；``TRENDING_PROXY`` 会同时用于 Trending 与 API。
        """
        self._token = token.strip()
        self._retry_delays = retry_delays
        self._proxy = proxy.strip() or None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        """创建底层 httpx 客户端（30 秒超时，可按需挂代理）。

        Returns:
            自身，便于 ``async with GitHubClient(...) as client``。
        """
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE, timeout=30.0, proxy=self._proxy
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        """关闭底层客户端并把引用置空，重复退出也不会报错。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_repository(self, full_name: str) -> GitHubRepository | None:
        """读取单个仓库元信息。

        Args:
            full_name: ``owner/name`` 形式，直接拼进路径，不做转义（值来自已解析的榜单）。

        Returns:
            仓库快照；仓库已删除或改名为私有（HTTP 404）时返回 ``None``，
            让上层把它计入失败数而不是抛异常中断整轮采集。

        Raises:
            GitHubAuthError: Token 无效。
            GitHubRateLimitError: 额度耗尽。
            GitHubRequestError: 其他状态码或传输失败。
        """
        response = await self._request(
            "GET",
            f"/repos/{full_name}",
            status_codes=[200, 404],
        )
        if response.status_code == 404:
            return None
        return GitHubRepository.from_payload(response.json())

    async def get_readme(self, full_name: str) -> str | None:
        """读取 README 原文，供中文简介生成使用。

        用 ``application/vnd.github.raw+json`` 直接拿 Markdown 源文本，避免再解码
        base64；结果截断到 ``README_MAX_CHARS``，防止单个仓库把提示词撑爆。

        Args:
            full_name: ``owner/name``。

        Returns:
            README 文本；仓库没有 README（404）或内容为空时返回 ``None``，
            简介生成会退化为只依据元信息撰写。
        """
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
        """查询核心接口的剩余额度与重置时间。

        采集结束前调用一次，结果写入 ``collection_runs``，便于事后判断这一轮是不是
        被限流截断。

        Returns:
            :class:`RateLimit`。

        Raises:
            GitHubRequestError: 查询本身失败（该调用不计入仓库失败数，由采集服务决定
                是否影响任务状态）。
        """
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
        """发送一次请求，并按错误类型决定重试还是立刻抛出。

        判定顺序很重要：先看状态码是否在 ``status_codes`` 白名单内（例如 404 对
        ``get_repository`` 是合法结果），再判断限流、鉴权、其他 4xx，最后才把 5xx
        与传输异常当作可重试错误。

        Args:
            method: HTTP 方法。
            url: 相对 ``GITHUB_API_BASE`` 的路径。
            params: 查询参数。
            status_codes: 视为成功的状态码列表，缺省仅 200。
            accept: 覆盖 ``Accept`` 头（README 需要 raw 媒体类型）。

        Returns:
            命中白名单的 httpx 响应。

        Raises:
            GitHubRateLimitError: 403 且 ``X-RateLimit-Remaining`` 为 0。
            GitHubAuthError: 401/403 且不是限流。
            GitHubRequestError: 其他 4xx，或重试后仍失败的 5xx / 传输异常。
        """
        assert self._client is not None
        allowed = status_codes or [200]
        headers = {
            "Accept": accept or ACCEPT_HEADER,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        last_exc: GitHubRequestError | None = None
        for attempt in range(len(self._retry_delays)):
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
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
    """判断 403 是“额度耗尽”还是“权限不足”。

    GitHub 两种情形都返回 403，只有 ``X-RateLimit-Remaining: 0`` 才是限流；
    区分开才能给出“等额度重置”而不是“换 Token”的建议。

    Args:
        response: 待判定的响应。

    Returns:
        状态码 403 且剩余额度为 0 时返回 ``True``。
    """
    return response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
