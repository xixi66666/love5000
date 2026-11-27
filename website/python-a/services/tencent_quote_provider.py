"""腾讯行情主数据源。

``TencentQuoteProvider.fetch`` 抓取 ``https://qt.gtimg.cn/q={sh|sz|bj}{code}`` 的
即时报文，返回价格、换手率、市盈率、振幅、市值、涨跌停价与量比。上游只提供 GBK
编码，中文股票名必须显式按 GBK 解码，否则会得到乱码。

报文形态是 ``v_sh600000="1~名称~...";``，字段以 ``~`` 分隔，本模块用到的下标为：
1 名称、3 现价、30 时间戳（yyyyMMddHHmmss）、38 换手率、39 市盈率 TTM、43 振幅、
44 总市值（亿元）、45 流通市值（亿元）、46 市净率、47 涨停价、48 跌停价、49 量比。
接口给出的市值已经是亿元，这里不再换算。

对外还提供两个小工具：``market_prefix``（代码到 sh/sz/bj 前缀，新浪资金流复用）与
``optional_float``（把 ``-`` 之类的占位符转成 ``None``）。

持久化：不写磁盘，结果由 ``StockResearchService`` 缓存。降级策略：请求失败原样向上
抛 ``ResearchProviderError``，由聚合层回退到东方财富；报文缺少 ``="`` 标记或字段数
不足 50 时也抛可重试异常，因为这类响应通常意味着上游临时改了返回格式。
"""

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
    """按代码首位推断交易所前缀。

    沪深北的代码段划分：6/9 开头为上海（``sh``），8 开头为北交所（``bj``），
    其余按深圳（``sz``）处理。这是各公开行情接口通用的经验规则，不做联网校验。

    Args:
        code: 6 位代码。

    Returns:
        ``sh`` / ``sz`` / ``bj``。

    Raises:
        ValueError: 代码不是 6 位数字。
    """
    value = validate_stock_code(code)
    if value.startswith(("6", "9")):
        return "sh"
    if value.startswith("8"):
        return "bj"
    return "sz"


def optional_float(value: Any) -> Optional[float]:
    """把报文字段转成浮点数，占位符与非法值返回 ``None``。

    腾讯用 ``-`` 表示停牌或不适用；区分 ``None`` 与 0 很重要，页面上停牌不应显示
    市盈率 0。

    Returns:
        解析成功返回浮点数；``None``、空串、``-`` 或无法解析时返回 ``None``。
    """
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TencentQuoteProvider:
    """腾讯即时行情提供方。

    实例只保存 HTTP 客户端，无状态，可跨线程共享；``provider_name`` 会写进
    ``success_block``，前端据此显示数据来源。
    """

    provider_name = "tencent"

    def __init__(self, http_client: Optional[Any] = None):
        """绑定 HTTP 客户端。

        Args:
            http_client: 具备 ``get_text`` 的客户端；为 ``None`` 时使用标准库实现，
                测试可注入桩以校验报文解析。
        """
        self.http_client = http_client or UrlLibHttpClient()

    def fetch(self, code: str) -> Dict[str, Any]:
        """抓取单只股票的即时行情快照。

        ``data_date`` 取自报文第 30 个字段的时间戳，只有前 8 位全是数字时才解析，
        因此停牌或字段错位时宁可不给日期也不给出错误日期。

        Args:
            code: 6 位代码，先校验再拼市场前缀。

        Returns:
            ``success_block`` 包装的行情字典，含 name / price / turnover_rate /
            pe_ttm / amplitude / market_cap_yi / float_market_cap_yi / pb /
            limit_up / limit_down / volume_ratio。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 网络失败或报文格式无效（字段数不足、缺少分隔符）。
        """
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
        """从 ``v_sh600000="..."`` 报文中切出 ``~`` 分隔的字段数组。

        先按 ``="`` 取引号内容再按 ``"`` 截断，比正则更快也更宽松（上游会把时间戳、
        名称等原样塞在中间）。字段数少于 50 直接判为格式无效，避免后续按下标取值时
        悄悄拿到 ``None``。

        Raises:
            ResearchProviderError: 缺少 ``="`` 标记或字段数不足，均标记为可重试。
        """
        text = str(payload or "")
        if '="' not in text:
            raise ResearchProviderError("腾讯行情返回格式无效", retryable=True)
        content = text.split('="', 1)[1].split('"', 1)[0]
        values = content.split("~")
        if len(values) < 50:
            raise ResearchProviderError("腾讯行情字段不完整", retryable=True)
        return values
