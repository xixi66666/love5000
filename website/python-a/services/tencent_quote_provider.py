from __future__ import annotations

from typing import Any, Dict, Optional

from services.research_provider import (
    ResearchProviderError,
    UrlLibHttpClient,
    success_block,
    validate_stock_code,
)


TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={}{}"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


def market_prefix(code: str) -> str:
    value = validate_stock_code(code)
    if value.startswith(("6", "9")):
        return "sh"
    if value.startswith("8"):
        return "bj"
    return "sz"


def optional_float(value: Any) -> Optional[float]:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TencentQuoteProvider:
    provider_name = "tencent"

    def __init__(self, http_client: Optional[Any] = None):
        self.http_client = http_client or UrlLibHttpClient()

    def fetch(self, code: str) -> Dict[str, Any]:
        value = validate_stock_code(code)
        prefix = market_prefix(value)
        url = TENCENT_QUOTE_URL.format(prefix, value)
        try:
            payload = self.http_client.get_text(
                url,
                headers=DEFAULT_HEADERS,
                encoding="gbk",
                timeout=10,
            )
        except ResearchProviderError:
            raise
        except Exception as exc:
            raise ResearchProviderError("腾讯行情请求失败：{}".format(exc), retryable=True) from exc

        values = self._parse_values(payload)
        timestamp = values[30].strip() if len(values) > 30 else ""
        data_date = None
        if len(timestamp) >= 8 and timestamp[:8].isdigit():
            data_date = "{}-{}-{}".format(timestamp[:4], timestamp[4:6], timestamp[6:8])
        data = {
            "name": values[1] or value,
            "price": optional_float(values[3]),
            "turnover_rate": optional_float(values[38]),
            "pe_ttm": optional_float(values[39]),
            "amplitude": optional_float(values[43]),
            "market_cap_yi": optional_float(values[44]),
            "float_market_cap_yi": optional_float(values[45]),
            "pb": optional_float(values[46]),
            "limit_up": optional_float(values[47]),
            "limit_down": optional_float(values[48]),
            "volume_ratio": optional_float(values[49]),
        }
        return success_block(self.provider_name, data, data_date=data_date)

    def _parse_values(self, payload: str):
        text = str(payload or "")
        if '="' not in text:
            raise ResearchProviderError("腾讯行情返回格式无效", retryable=True)
        content = text.split('="', 1)[1].split('"', 1)[0]
        values = content.split("~")
        if len(values) < 50:
            raise ResearchProviderError("腾讯行情字段不完整", retryable=True)
        return values
