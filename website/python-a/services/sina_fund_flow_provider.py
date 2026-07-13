"""新浪资金流备用 Provider，端点映射参考 a-stock-data V3.4.0。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from services.research_provider import ResearchProviderError, UrlLibHttpClient, success_block, validate_stock_code
from services.tencent_quote_provider import market_prefix


SINA_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "MoneyFlow.ssl_qsfx_zjlrqs?page=1&num=60&sort=opendate&asc=0&daima={}{}"
)


class SinaFundFlowProvider:
    provider_name = "sina"

    def __init__(self, http_client: Optional[Any] = None):
        self.http_client = http_client or UrlLibHttpClient()

    def fetch(self, code: str) -> Dict[str, Any]:
        value = validate_stock_code(code)
        try:
            payload = self.http_client.get_text(
                SINA_URL.format(market_prefix(value), value),
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
                encoding="utf-8",
                timeout=15,
            )
            start = payload.index("[")
            end = payload.rindex("]") + 1
            raw_rows = json.loads(payload[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ResearchProviderError("新浪资金流返回格式无效") from exc
        except ResearchProviderError:
            raise
        except Exception as exc:
            raise ResearchProviderError("新浪资金流请求失败：{}".format(exc)) from exc
        rows = []
        for raw in raw_rows:
            try:
                net = float(raw.get("netamount") or 0.0)
            except (TypeError, ValueError):
                net = 0.0
            rows.append({"date": str(raw.get("opendate") or ""), "main_net": net})
        if not rows:
            raise ResearchProviderError("新浪资金流暂无数据", retryable=False)
        ordered = list(reversed(rows))
        values = [row["main_net"] for row in ordered]
        five_day = sum(values[-5:])
        twenty_day = sum(values[-20:])
        data = {
            "today_main_net": values[-1],
            "five_day_net": five_day,
            "five_day_direction": self._direction(five_day),
            "twenty_day_net": twenty_day,
            "twenty_day_direction": self._direction(twenty_day),
        }
        return success_block(self.provider_name, data, data_date=ordered[-1]["date"])

    def _direction(self, value: float) -> str:
        if value > 0:
            return "净流入"
        if value < 0:
            return "净流出"
        return "持平"
