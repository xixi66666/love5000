"""新浪资金流备用数据源。

``SinaFundFlowProvider.fetch`` 抓取新浪的资金流历史接口，返回与东方财富
``fetch_fund_flow`` 完全相同的摘要结构（今日、5 日、20 日主力净流入及方向），
因此 ``StockResearchService`` 可以在东方财富失败时无感切换，前端不需要分支。

上游返回的是一段“JS 变量包着数组字面量”的文本，不是标准 JSON，所以先取第一个
``[`` 到最后一个 ``]`` 再解析；接口按日期倒序返回，这里反转成升序后再取尾部窗口，
与东方财富“最近 N 天”的语义保持一致。

数据来源：新浪财经公开接口，端点为 ``SINA_URL``。持久化：不写磁盘。降级策略：
缺少数组括号、JSON 非法、请求失败都收敛成 ``ResearchProviderError``；空数组标记为
不可重试，因为重试同样拿不到数据。
"""

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
    """新浪资金流备用提供方，只在东方财富资金流失败时被调用。"""

    provider_name = "sina"

    def __init__(self, http_client: Optional[Any] = None):
        """绑定 HTTP 客户端。

        Args:
            http_client: 具备 ``get_text`` 的客户端；为 ``None`` 时使用标准库实现，
                测试可注入桩以喂入固定的新浪报文。
        """
        self.http_client = http_client or UrlLibHttpClient()

    def fetch(self, code: str) -> Dict[str, Any]:
        """抓取单只股票的资金流摘要。

        解析失败分两类处理：截取数组或 JSON 解析抛出的 ``ValueError`` 统一转成
        “返回格式无效”，``ResearchProviderError``（网络层）原样上抛，其余异常兜底
        成“请求失败”，保证调用方只需要认识一种异常类型。

        Args:
            code: 6 位代码，校验后与市场前缀一起拼进查询串。

        Returns:
            ``success_block`` 包装的摘要，字段为 ``today_main_net``、
            ``five_day_net``、``five_day_direction``、``twenty_day_net``、
            ``twenty_day_direction``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 上游不含数组、JSON 非法、请求失败或结果为空。
        """
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
        """把净流入金额映射成中文方向词：正为净流入、负为净流出、零为持平。"""
        if value > 0:
            return "净流入"
        if value < 0:
            return "净流出"
        return "持平"
