"""东方财富研究数据 Provider。

端点字段映射参考 simonlin1212/a-stock-data V3.4.0（Apache-2.0），在此项目中改为
Python 标准库客户端、线程安全限流和结构化异常。

对外提供 ``EastmoneyResearchProvider`` 的六个查询：``fetch_overview``（估值与行情）、
``fetch_fund_flow``（主力资金流）、``fetch_margin``（融资融券）、
``fetch_shareholders``（股东户数）、``fetch_lockups``（未来解禁）、
``fetch_reports``（个股研报）。模块内的 ``_float`` / ``_scaled`` / ``_direction``
只服务于这些查询，把上游的字符串字段和放大 100 倍的定点数还原成业务单位。

端点：``QUOTE_URL``（push2 即时行情）、``FUND_FLOW_URL``（资金流日 K）、
``DATACENTER_URL``（datacenter-web 通用报表，融资融券 / 股东户数 / 解禁共用）、
``REPORT_URL``（研报列表）；研报 PDF 统一指向 ``pdf.dfcfw.com`` 并经白名单校验。

持久化：不写磁盘，结果由 ``StockResearchService`` 缓存。降级策略：所有请求先过
``EastmoneyRateLimiter``（默认 1 秒间隔），可重试错误最多尝试两次；最终失败统一抛
``ResearchProviderError``，由聚合层换成失败块或切备用源。“暂无数据”类结果标记为
不可重试，避免无意义的重复请求。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.research_provider import (
    EastmoneyRateLimiter,
    ResearchProviderError,
    UrlLibHttpClient,
    is_safe_external_url,
    success_block,
    validate_stock_code,
)


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
FUND_FLOW_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_URL = "https://reportapi.eastmoney.com/report/list"
REPORT_PDF_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{}_1.pdf"


def _float(value: Any) -> Optional[float]:
    """把上游字段转成浮点数，``-`` 等占位符与非法值返回 ``None``。

    东方财富在停牌、无估值或新上市时会返回 ``-``，直接 ``float()`` 会抛异常；这里统一
    退化为 ``None``，让页面显示“暂无”而不是伪造的 0。

    Returns:
        解析成功返回浮点数；空值、``-`` 或无法解析时返回 ``None``。
    """
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scaled(value: Any, divisor: float = 100.0) -> Optional[float]:
    """把放大存储的定点数还原成业务值并保留 4 位小数。

    东方财富行情接口把价格、市盈率、振幅等统一放大 100 倍（市值以元为单位），因此
    默认除以 100；市值类字段传 ``100000000`` 得到“亿元”。

    Args:
        value: 上游原始字段。
        divisor: 放大倍数。

    Returns:
        归一化后的数值；原值为空或非法时返回 ``None``。
    """
    number = _float(value)
    return round(number / divisor, 4) if number is not None else None


def _direction(value: float) -> str:
    """把净流入金额映射成中文方向词：正为净流入、负为净流出、零为持平。"""
    if value > 0:
        return "净流入"
    if value < 0:
        return "净流出"
    return "持平"


class EastmoneyResearchProvider:
    """东方财富研究数据提供方。

    持有 HTTP 客户端与限流器，本身无状态，可跨线程共享。限流器按实例独立计数，
    多建实例会成倍提高整体请求速率，不要用它规避上游限速。

    Attributes:
        provider_name: 写进 ``success_block`` 的来源标识，固定为 ``eastmoney``。
    """

    provider_name = "eastmoney"

    def __init__(self, http_client: Optional[Any] = None, limiter: Optional[EastmoneyRateLimiter] = None):
        """绑定 HTTP 客户端与限流器。

        Args:
            http_client: 具备 ``get_json`` 的客户端；为 ``None`` 时用标准库实现。
            limiter: 请求限流器；为 ``None`` 时新建一个默认 1 秒间隔的实例，
                测试可注入不睡眠的桩以加速。
        """
        self.http_client = http_client or UrlLibHttpClient()
        self.limiter = limiter or EastmoneyRateLimiter()

    def _get_json(self, url: str, params: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
        """带限流与一次重试的 GET JSON。

        ``ResearchProviderError`` 是否重试取决于它的 ``retryable``：限流与 5xx 值得再试
        一次，参数错误之类直接抛出；其他异常在最后一次尝试时包装成
        ``ResearchProviderError``，让调用方只需要认识一种异常类型。每次尝试都单独占用
        限流时间片，重试同样受频率约束。

        Raises:
            ResearchProviderError: 两次都失败，或错误被标记为不可重试。
        """
        headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
        last_error = None
        for attempt in range(2):
            try:
                with self.limiter.slot():
                    return self.http_client.get_json(url, params=params, headers=headers, timeout=timeout)
            except ResearchProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt == 1:
                    raise
            except Exception as exc:
                last_error = exc
                if attempt == 1:
                    raise ResearchProviderError("东方财富请求失败：{}".format(exc)) from exc
        raise ResearchProviderError("东方财富请求失败：{}".format(last_error))

    def fetch_overview(self, code: str) -> Dict[str, Any]:
        """取估值与行情概要。

        一次请求带全部需要的字段码：f43 现价、f9 市盈率 TTM、f23 市净率、f20 总市值、
        f21 流通市值、f10 量比、f171 振幅、f51 / f52 涨停跌停价、f58 名称、f124 行情
        时间戳。除市值外都按放大 100 倍处理，市值按元除以 1e8 得到亿元。

        Args:
            code: 6 位代码，用于拼 ``secid``。

        Returns:
            ``success_block`` 包装的行情字典；``data_date`` 取自 ``f124``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 请求失败，或响应里没有 ``data`` 对象（常见于停牌或
                代码不存在）。
        """
        value = validate_stock_code(code)
        payload = self._get_json(
            QUOTE_URL,
            {
                "secid": self._secid(value),
                "fields": "f9,f10,f20,f21,f23,f43,f51,f52,f58,f124,f171",
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ResearchProviderError("东方财富行情返回为空")
        timestamp = _float(data.get("f124"))
        data_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d") if timestamp else None
        result = {
            "name": data.get("f58") or value,
            "price": _scaled(data.get("f43")),
            "pe_ttm": _scaled(data.get("f9")),
            "pb": _scaled(data.get("f23")),
            "market_cap_yi": _scaled(data.get("f20"), 100000000.0),
            "float_market_cap_yi": _scaled(data.get("f21"), 100000000.0),
            "volume_ratio": _scaled(data.get("f10")),
            "amplitude": _scaled(data.get("f171")),
            "limit_up": _scaled(data.get("f51")),
            "limit_down": _scaled(data.get("f52")),
        }
        return success_block(self.provider_name, result, data_date=data_date)

    def fetch_fund_flow(self, code: str) -> Dict[str, Any]:
        """取最近 120 个交易日的主力资金流并汇总。

        上游用 ``klines`` 返回以逗号分隔的字符串行，第 1 个字段是日期、第 2 个是主力
        净流入（元）；行内字段不足 6 个说明格式异常，直接跳过。``data_date`` 取最后一
        行的日期，因为上游按日期升序返回。

        Args:
            code: 6 位代码。

        Returns:
            ``success_block`` 包装的摘要，见 ``_fund_flow_summary``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 请求失败，或过滤后没有任何有效行。
        """
        value = validate_stock_code(code)
        payload = self._get_json(
            FUND_FLOW_URL,
            {
                "secid": self._secid(value),
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                "lmt": "120",
            },
        )
        raw_rows = (payload.get("data") or {}).get("klines") or []
        rows = []
        for raw in raw_rows:
            parts = str(raw).split(",")
            if len(parts) < 6:
                continue
            rows.append({"date": parts[0], "main_net": _float(parts[1]) or 0.0})
        if not rows:
            raise ResearchProviderError("东方财富资金流暂无数据")
        return success_block(self.provider_name, self._fund_flow_summary(rows), data_date=rows[-1]["date"])

    def fetch_margin(self, code: str, page_size: int = 30) -> Dict[str, Any]:
        """取融资融券余额及其日变化。

        报表 ``RPTA_WEB_RZRQ_GGMX`` 按 ``DATE`` 倒序，第一行是最新交易日：``RZYE`` 为
        融资余额、``RZRQYE`` 为融资融券余额；``balance_change`` 用最新与次新两行相减，
        只有一行时留 ``None`` 而不是 0。

        Args:
            code: 6 位代码。
            page_size: 取多少天的数据，只为拿到“上一日”做差，默认 30 天足够覆盖长假。

        Returns:
            ``success_block`` 包装的 ``{latest_balance, balance_change, total_balance}``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 请求失败，或报表返回空（不可重试）。
        """
        rows = self._datacenter(
            "RPTA_WEB_RZRQ_GGMX",
            '(SCODE="{}")'.format(validate_stock_code(code)),
            page_size,
            "DATE",
        )
        if not rows:
            raise ResearchProviderError("融资融券暂无数据", retryable=False)
        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else {}
        latest_balance = _float(latest.get("RZYE"))
        previous_balance = _float(previous.get("RZYE"))
        change = None
        if latest_balance is not None and previous_balance is not None:
            change = latest_balance - previous_balance
        data_date = str(latest.get("DATE") or "")[:10] or None
        return success_block(
            self.provider_name,
            {
                "latest_balance": latest_balance,
                "balance_change": change,
                "total_balance": _float(latest.get("RZRQYE")),
            },
            data_date=data_date,
        )

    def fetch_shareholders(self, code: str, page_size: int = 10) -> Dict[str, Any]:
        """取最新一期股东户数。

        报表 ``RPT_HOLDERNUMLATEST`` 按 ``END_DATE`` 倒序，第一行即最新报告期：
        ``HOLDER_NUM`` 为股东户数、``HOLDER_NUM_RATIO`` 为户数变化比例、
        ``AVG_FREE_SHARES`` 为户均持股。户数缺失时按 0 处理，比例与户均保持 ``None``，
        便于前端区分“没有数据”和“确为 0”。

        Args:
            code: 6 位代码。
            page_size: 取多少期，默认 10 期。

        Returns:
            ``success_block`` 包装的 ``{holder_count, change_ratio, average_shares}``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 请求失败，或报表返回空（不可重试）。
        """
        rows = self._datacenter(
            "RPT_HOLDERNUMLATEST",
            '(SECURITY_CODE="{}")'.format(validate_stock_code(code)),
            page_size,
            "END_DATE",
        )
        if not rows:
            raise ResearchProviderError("股东户数暂无数据", retryable=False)
        latest = rows[0]
        data_date = str(latest.get("END_DATE") or "")[:10] or None
        return success_block(
            self.provider_name,
            {
                "holder_count": int(_float(latest.get("HOLDER_NUM")) or 0),
                "change_ratio": _float(latest.get("HOLDER_NUM_RATIO")),
                "average_shares": _float(latest.get("AVG_FREE_SHARES")),
            },
            data_date=data_date,
        )

    def fetch_lockups(self, code: str, today: Optional[str] = None, forward_days: int = 90) -> Dict[str, Any]:
        """取未来一段时间内的限售解禁安排。

        报表 ``RPT_LIFT_STAGE`` 用 ``FREE_DATE`` 区间过滤（含首尾），并按日期升序
        （``sort_types="1"``）返回，因此第一行是最近一次解禁。没有解禁安排时
        ``data_date`` 退化为起始日期，避免返回 ``None`` 让前端误判为“数据缺失”。

        Args:
            code: 6 位代码。
            today: 起始日期 ``YYYY-MM-DD``；为空时取本机当天。
            forward_days: 向后看多少天，默认 90 天。

        Returns:
            ``success_block`` 包装的 ``{upcoming: [...]}``，每项含日期、股份类型、
            解禁股数、可流通股数与占比。

        Raises:
            ValueError: 代码格式不合法，或 ``today`` 不是 ``YYYY-MM-DD``。
            ResearchProviderError: 请求失败。
        """
        start = datetime.strptime(today, "%Y-%m-%d") if today else datetime.now()
        end = start + timedelta(days=forward_days)
        filter_str = '(SECURITY_CODE="{}")(FREE_DATE>=\'{}\')(FREE_DATE<=\'{}\')'.format(
            validate_stock_code(code), start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        )
        rows = self._datacenter("RPT_LIFT_STAGE", filter_str, 20, "FREE_DATE", sort_types="1")
        upcoming = []
        for row in rows:
            upcoming.append(
                {
                    "date": str(row.get("FREE_DATE") or "")[:10],
                    "type": row.get("FREE_SHARES_TYPE") or "",
                    "shares": _float(row.get("FREE_SHARES")),
                    "able_shares": _float(row.get("ABLE_FREE_SHARES")),
                    "ratio": _float(row.get("FREE_RATIO")),
                }
            )
        data_date = upcoming[0]["date"] if upcoming else start.strftime("%Y-%m-%d")
        return success_block(self.provider_name, {"upcoming": upcoming}, data_date=data_date)

    def fetch_reports(self, code: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """取个股研报列表。

        评分、行业、评级变更全部用 ``*`` 表示不限，时间区间放宽到 2000–2030 以覆盖全部
        历史；``qType=0`` 表示按发布时间排序。单次超时放宽到 30 秒，因为研报列表响应
        体明显大于其它接口。PDF 地址由 ``infoCode`` 套 ``REPORT_PDF_TEMPLATE`` 生成，
        再过 ``pdf.dfcfw.com`` 白名单。

        Args:
            code: 6 位代码。
            page: 页码，从 1 开始。
            page_size: 每页条数。

        Returns:
            ``success_block`` 包装的 ``{items, page, page_size, has_more}``；
            ``has_more`` 由上游 ``TotalPage`` 判断。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 请求失败或返回非法 JSON。
        """
        value = validate_stock_code(code)
        payload = self._get_json(
            REPORT_URL,
            {
                "industryCode": "*",
                "pageSize": str(page_size),
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": str(page),
                "qType": "0",
                "code": value,
            },
            timeout=30,
        )
        records = payload.get("data") or []
        items = []
        allowed = {"pdf.dfcfw.com"}
        for record in records:
            info_code = str(record.get("infoCode") or "").strip()
            url = REPORT_PDF_TEMPLATE.format(info_code) if info_code else ""
            items.append(
                {
                    "title": str(record.get("title") or ""),
                    "organization": str(record.get("orgSName") or ""),
                    "rating": str(record.get("emRatingName") or ""),
                    "date": str(record.get("publishDate") or "")[:10],
                    "eps_forecast": _float(record.get("predictThisYearEps")),
                    "url": url if is_safe_external_url(url, allowed) else None,
                }
            )
        data_date = items[0]["date"] if items else None
        return success_block(
            self.provider_name,
            {
                "items": items,
                "page": page,
                "page_size": page_size,
                "has_more": page < int(payload.get("TotalPage") or page),
            },
            data_date=data_date,
        )

    def _datacenter(
        self,
        report_name: str,
        filter_str: str,
        page_size: int,
        sort_columns: str,
        sort_types: str = "-1",
    ) -> List[Dict[str, Any]]:
        """datacenter-web 通用报表查询。

        融资融券、股东户数、解禁三个接口共用同一套参数形态：``reportName`` 指定报表，
        ``columns=ALL`` 取全字段，``filter`` 是上游自有的过滤表达式语法（形如
        ``(SECURITY_CODE="600000")``），``sortColumns`` / ``sortTypes`` 控制排序。

        Args:
            report_name: 上游报表名。
            filter_str: 上游过滤表达式，调用方负责拼接并已校验代码。
            page_size: 返回行数上限。
            sort_columns: 排序字段。
            sort_types: ``-1`` 倒序、``1`` 升序。

        Returns:
            报表数据行；``result`` 或 ``data`` 缺失、或结果不是列表时返回空列表，
            由调用方决定是否视为错误。
        """
        payload = self._get_json(
            DATACENTER_URL,
            {
                "reportName": report_name,
                "columns": "ALL",
                "filter": filter_str,
                "pageNumber": "1",
                "pageSize": str(page_size),
                "sortColumns": sort_columns,
                "sortTypes": sort_types,
                "source": "WEB",
                "client": "WEB",
            },
        )
        result = payload.get("result") or {}
        rows = result.get("data") or []
        return rows if isinstance(rows, list) else []

    def _fund_flow_summary(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """把逐日主力净流入汇总成今日、5 日与 20 日口径。

        窗口取列表尾部（``rows`` 已按日期升序），不足 5 天或 20 天时就是全部可用天数，
        不补 0——补 0 会让“净流入”被人为稀释。返回的金额单位是元。
        """
        values = [float(row.get("main_net") or 0.0) for row in rows]
        five_day = sum(values[-5:])
        twenty_day = sum(values[-20:])
        return {
            "today_main_net": values[-1],
            "five_day_net": five_day,
            "five_day_direction": _direction(five_day),
            "twenty_day_net": twenty_day,
            "twenty_day_direction": _direction(twenty_day),
        }

    def _secid(self, code: str) -> str:
        """拼东方财富的 ``secid``：6 / 9 开头为沪市（``1.``），其余为深市或北交所（``0.``）。"""
        market = "1" if code.startswith(("6", "9")) else "0"
        return "{}.{}".format(market, code)
