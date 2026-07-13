from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, Iterable, Optional


class ResearchProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True, status_code: Optional[int] = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class UrlLibHttpClient:
    def get_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        encoding: str = "utf-8",
        timeout: int = 15,
    ) -> str:
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


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def validate_stock_code(code: Any) -> str:
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
    return {
        "success": True,
        "provider": provider,
        "fallback_used": fallback_used,
        "data_date": data_date,
        "fetched_at": now_iso(),
        "data": data,
    }


def failure_block(message: str, retryable: bool = True) -> Dict[str, Any]:
    return {
        "success": False,
        "message": str(message),
        "provider": None,
        "retryable": retryable,
    }


def is_safe_external_url(url: str, allowed_domains: Iterable[str]) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    domains = {str(domain).lower() for domain in allowed_domains}
    return hostname in domains
