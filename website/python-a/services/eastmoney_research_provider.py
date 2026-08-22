"""东方财富研究数据 Provider。

端点字段映射参考 simonlin1212/a-stock-data V3.4.0（Apache-2.0），
在此项目中改为 Python 标准库客户端、线程安全限流和结构化异常。
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
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scaled(value: Any, divisor: float = 100.0) -> Optional[float]:
    number = _float(value)
    return round(number / divisor, 4) if number is not None else None


def _direction(value: float) -> str:
    if value > 0:
        return "净流入"
    if value < 0:
        return "净流出"
    return "持平"


class EastmoneyResearchProvider:
    provider_name = "eastmoney"

    def __init__(self, http_client: Optional[Any] = None, limiter: Optional[EastmoneyRateLimiter] = None):
        self.http_client = http_client or UrlLibHttpClient()
        self.limiter = limiter or EastmoneyRateLimiter()

    def _get_json(self, url: str, params: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
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
        market = "1" if code.startswith(("6", "9")) else "0"
        return "{}.{}".format(market, code)
