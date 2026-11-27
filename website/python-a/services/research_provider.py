"""上游研究数据源的公共基础设施。

对外提供四组能力：

- ``ResearchProviderError``：统一的提供方异常，带 ``retryable`` 与可选的
  ``status_code``，让聚合层能区分“稍后重试”和“本块直接降级”。
- ``UrlLibHttpClient``：只依赖 urllib 的 HTTP 客户端，支持取文本、取 JSON、表单
  POST 与 JSON POST，全部带超时，并把网络与解析失败收敛成 ``ResearchProviderError``。
- ``EastmoneyRateLimiter``：线程安全的固定间隔限流器，因为东方财富对高频请求敏感。
- 模块级工具：``now_iso``、``validate_stock_code``、``success_block``、
  ``failure_block``、``is_safe_external_url``。

数据来源：腾讯、东方财富、新浪、巨潮与交易所的公开行情和公告接口，端点与字段映射
由各 provider 模块维护。持久化：本模块不写磁盘，结果要么进入
``StockResearchService`` 的内存缓存，要么由 ``server.py`` 转成响应返回。

降级策略：HTTP 4xx（429 除外）标记为不可重试；5xx、429、超时、DNS 失败、连接
重置、非法 JSON 以及 JSON 根不是对象都标记为可重试。``success_block`` 与
``failure_block`` 统一了成功/失败块的骨架，上游失败只影响单个数据块，不会让整个
股票详情页报错。
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, Optional


class ResearchProviderError(RuntimeError):
    """上游数据源异常。

    Attributes:
        retryable: 是否值得重试。429、5xx、超时与解析失败为 ``True``；其余 4xx 与
            “暂无数据”为 ``False``，重试只会浪费时间。
        status_code: 上游 HTTP 状态码；网络层失败时为 ``None``。
    """

    def __init__(self, message: str, retryable: bool = True, status_code: Optional[int] = None):
        """记录可重试性与状态码。

        Args:
            message: 面向日志与用户的中文说明，不含上游响应正文，避免把大段 HTML
                或凭据信息带进日志。
            retryable: 是否值得重试。
            status_code: 上游 HTTP 状态码；非 HTTP 失败留空。
        """
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class UrlLibHttpClient:
    """基于 urllib 的极简 HTTP 客户端。

    只依赖标准库，便于在没装第三方依赖的机器上直接启动。不保持连接、不内建重试，
    重试策略留给 provider，因为不同接口的失败成本和限流要求不同。实例无状态，
    可跨线程共享。
    """

    def _read_json(self, request: urllib.request.Request, timeout: int) -> Dict[str, Any]:
        """发送请求并把响应体解析成 JSON 对象。

        Args:
            request: 已设置 URL、方法与请求头的请求对象。
            timeout: 单次请求超时秒数，透传给 ``urlopen``。

        Returns:
            解析后的字典；JSON 根不是对象也视为无效，因为所有调用方都按下标取字段。

        Raises:
            ResearchProviderError: HTTP 非 2xx（带状态码与可重试性）、网络层失败、
                响应不是合法 JSON，或 JSON 根不是对象。
        """
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise ResearchProviderError(
                "外部数据源返回 HTTP {}".format(exc.code),
                retryable=exc.code == 429 or exc.code >= 500,
                status_code=exc.code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ResearchProviderError("外部数据源请求失败：{}".format(exc), retryable=True) from exc
        try:
            result = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ResearchProviderError("外部数据源返回了无效 JSON", retryable=True) from exc
        if not isinstance(result, dict):
            raise ResearchProviderError("外部数据源 JSON 结构无效", retryable=True)
        return result

    def get_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        encoding: str = "utf-8",
        timeout: int = 15,
    ) -> str:
        """取纯文本响应。

        腾讯行情只返回 GBK，新浪资金流返回的是包在 JS 变量里的数组字面量，两者都走
        这里；``errors="replace"`` 保证个别乱码字节不会让整次请求失败。

        Args:
            url: 完整地址。
            headers: 额外请求头，通常带 UA 与 Referer；部分接口缺 Referer 会被拒。
            encoding: 响应解码方式，腾讯行情需要传 ``gbk``。
            timeout: 单次请求超时秒数。

        Returns:
            解码后的响应文本。

        Raises:
            ResearchProviderError: HTTP 非 2xx，或连接、超时等网络层失败。
        """
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode(encoding, errors="replace")
        except urllib.error.HTTPError as exc:
            raise ResearchProviderError(
                "外部数据源返回 HTTP {}".format(exc.code),
                retryable=exc.code == 429 or exc.code >= 500,
                status_code=exc.code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ResearchProviderError("外部数据源请求失败：{}".format(exc), retryable=True) from exc

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """GET 请求，把查询参数拼到 URL 上后返回 JSON 对象。

        ``urlencode`` 负责转义中文与特殊字符；地址里已有 ``?`` 时改用 ``&`` 继续
        拼接，因此调用方可以传带固定参数的地址。

        Args:
            url: 基础地址。
            params: 查询参数字典，值为 ``None`` 时仍会被编码。
            headers: 额外请求头。
            timeout: 单次请求超时秒数。

        Returns:
            解析后的 JSON 对象。

        Raises:
            ResearchProviderError: 同 ``_read_json``。
        """
        target = url
        if params:
            separator = "&" if "?" in target else "?"
            target = target + separator + urllib.parse.urlencode(params)
        return self._read_json(urllib.request.Request(target, headers=headers or {}), timeout)

    def post_form_json(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """以 ``application/x-www-form-urlencoded`` 提交并解析 JSON。

        巨潮公告查询接口只接受表单编码，因此单独保留这个方法，而不是复用 JSON POST。
        调用方未显式给 ``Content-Type`` 时补上默认值，显式给了就尊重调用方。

        Raises:
            ResearchProviderError: 同 ``_read_json``。
        """
        request_headers = dict(headers or {})
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        body = urllib.parse.urlencode(data or {}).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        return self._read_json(request, timeout)

    def post_json(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """以 ``application/json`` 提交并解析 JSON。

        深交所公告接口要求 JSON 请求体；``ensure_ascii=False`` 让中文按 UTF-8 直传，
        与上游示例负载一致。

        Raises:
            ResearchProviderError: 同 ``_read_json``。
        """
        request_headers = dict(headers or {})
        request_headers.setdefault("Content-Type", "application/json")
        body = json.dumps(data or {}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        return self._read_json(request, timeout)


class EastmoneyRateLimiter:
    """固定最小间隔的线程安全限流器。

    东方财富对短时间高频请求会限流甚至临时拒绝，所以同一进程内所有请求共享一个
    间隔（默认 1 秒）。``monotonic`` 与 ``sleep`` 可注入，测试无需真的等待。
    """

    def __init__(self, min_interval: float = 1.0, monotonic=None, sleep=None):
        """配置间隔与时钟。

        Args:
            min_interval: 两次请求之间的最小间隔秒数。
            monotonic: 单调时钟函数，默认 ``time.monotonic``；用单调时钟可避免系统
                对时让间隔计算变成负数。
            sleep: 睡眠函数，默认 ``time.sleep``，测试可替换成记录调用的桩。
        """
        self.min_interval = min_interval
        self.monotonic = monotonic or time.monotonic
        self.sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._last_call = None

    @contextmanager
    def slot(self):
        """占用一个请求时间片，退出时刷新上次调用时间。

        整个 ``with`` 体（包含真实网络请求）都在锁内，并发线程因此被串行化到同一
        节奏；``finally`` 用退出时刻的单调时间刷新 ``_last_call``，把请求耗时也算进
        间隔，避免慢请求结束后立刻再发。异常照常向上冒泡，但限流状态仍会更新。
        """
        with self._lock:
            now = self.monotonic()
            if self._last_call is not None:
                wait = self.min_interval - (now - self._last_call)
                if wait > 0:
                    self.sleep(wait)
            try:
                yield
            finally:
                self._last_call = self.monotonic()


def now_iso() -> str:
    """返回带本机时区的 ISO 8601 时间戳（秒精度），用于 ``fetched_at`` 等字段。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def validate_stock_code(code: Any) -> str:
    """校验并返回 6 位纯数字 A 股代码。

    所有 provider 入口都先过这一层，避免把用户输入直接拼进上游 URL。

    Args:
        code: 任意类型的代码输入，内部先转字符串并去空白。

    Returns:
        规范化后的 6 位代码字符串。

    Raises:
        ValueError: 不是 6 位数字，提示信息为中文，由 HTTP 处理器转成 400 响应。
    """
    value = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError("股票代码必须是 6 位数字")
    return value


def success_block(
    provider: str,
    data: Dict[str, Any],
    data_date: Optional[str] = None,
    fallback_used: bool = False,
) -> Dict[str, Any]:
    """包装一个成功的数据块。

    统一骨架让前端不必按 provider 分支：``provider`` 说明数据来自哪家，
    ``data_date`` 是数据自身的最新日期（不是抓取时间），``fetched_at`` 是抓取时间，
    ``fallback_used`` 标记是否用了备用源。

    Args:
        provider: 提供方标识，如 ``tencent`` / ``eastmoney`` / ``sina``。
        data: 归一化后的业务字段。
        data_date: 数据日期 ``YYYY-MM-DD``；上游没给时为 ``None``。
        fallback_used: 是否为备用源结果。

    Returns:
        可直接放进 section 的 ``blocks`` 的字典。
    """
    return {
        "success": True,
        "provider": provider,
        "fallback_used": fallback_used,
        "data_date": data_date,
        "fetched_at": now_iso(),
        "data": data,
    }


def failure_block(message: str, retryable: bool = True) -> Dict[str, Any]:
    """包装一个失败的数据块。

    失败块不带 ``provider`` 与 ``data``，只给中文原因和可重试性；聚合层据此决定页面
    显示“稍后重试”还是“暂无数据”，同一 section 里的其他数据块照常展示。

    Args:
        message: 面向用户的中文说明。
        retryable: 是否值得重试。

    Returns:
        失败块字典；``provider`` 固定为 ``None``，与成功块保持同构。
    """
    return {
        "success": False,
        "message": str(message),
        "provider": None,
        "retryable": retryable,
    }


def is_safe_external_url(url: str, allowed_domains: Iterable[str]) -> bool:
    """判断上游给出的链接是否可以交给前端渲染或下载。

    只接受 https 且主机名与白名单完全一致（不做后缀匹配），防止上游返回 ``http://``、
    ``file://`` 或仿冒域名被页面直接渲染成可点击地址。白名单按域名硬编码在各
    provider 里，上游更换域名时需要同步修改。

    Args:
        url: 待检查的链接。
        allowed_domains: 允许的主机名集合，比较时统一转小写。

    Returns:
        通过返回 ``True``；解析失败、协议不是 https、缺少主机名或不在白名单返回
        ``False``。
    """
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    domains = {str(domain).lower() for domain in allowed_domains}
    return hostname in domains
