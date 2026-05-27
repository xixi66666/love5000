import math
from datetime import date, datetime, timedelta
from typing import List, Optional

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


AKSHARE_INSTALL_MESSAGE = "AkShare is not installed. Run: python -m pip install -r requirements.txt"


class AkShareProvider:
    """AkShare backed full-market data provider.

    第一阶段只做快速接入：日行情来自 AkShare，估值和财务使用明确标记的中性占位数据，
    避免把派生数据误认为真实估值或真实财报。
    """

    name = "akshare"

    def __init__(self, timeout_seconds: int = 15):
        today = date.today().strftime("%Y%m%d")
        self.timeout_seconds = timeout_seconds
        self.data_version = "akshare-%s" % today
        self.errors = []
        self.warnings = []

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        # 第一版用工作日近似交易日，法定节假日休市可能不完整，后续替换为交易所日历。
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                days.append(current.isoformat())
            current += timedelta(days=1)
        rows = []
        for index, day in enumerate(days):
            next_day = days[index + 1] if index + 1 < len(days) else None
            rows.append(TradeCalendarRow(
                trade_date=day,
                is_open=True,
                prev_trade_date=days[index - 1] if index > 0 else None,
                next_trade_date=next_day,
                is_month_end=next_day is None or next_day[:7] != day[:7],
            ))
        return rows

    def get_stock_basic(self) -> List[StockBasicRow]:
        ak = self._akshare()
        df = ak.stock_info_a_code_name()
        rows = []
        for item in df.to_dict("records"):
            code = self._clean_code(self._pick(item, ["code", "代码", "证券代码"]))
            name = str(self._pick(item, ["name", "名称", "证券简称"]) or "").strip()
            if not code or not name:
                continue
            rows.append(StockBasicRow(
                code=code,
                name=name,
                exchange=self._infer_exchange(code),
                list_date="1990-01-01",
                delist_date=None,
                status="listed",
                industry="未分类",
                is_st="ST" in name.upper(),
            ))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        ak = self._akshare()
        self.errors = []
        calendar_by_date = {row.trade_date: row for row in self.get_trade_calendar(start_date, end_date)}
        rows = []
        for stock in self.get_stock_basic():
            try:
                df = ak.stock_zh_a_hist(
                    symbol=stock.code,
                    period="daily",
                    start_date=self._compact_date(start_date),
                    end_date=self._compact_date(end_date),
                    adjust="qfq",
                )
            except Exception as exc:
                self.errors.append({"code": stock.code, "message": str(exc)})
                continue

            for item in df.to_dict("records"):
                trade_date = self._normalize_date(self._pick(item, ["日期", "date", "trade_date"]))
                if not trade_date or trade_date < start_date or trade_date > end_date:
                    continue
                pre_close = self._pre_close(item)
                calendar_row = calendar_by_date.get(trade_date)
                rows.append(DailyBarRow(
                    trade_date=trade_date,
                    code=stock.code,
                    open=self._float(item, ["开盘", "open"]),
                    high=self._float(item, ["最高", "high"]),
                    low=self._float(item, ["最低", "low"]),
                    close=self._float(item, ["收盘", "close"]),
                    pre_close=pre_close,
                    volume=self._float(item, ["成交量", "volume"]),
                    amount=self._float(item, ["成交额", "amount"]),
                    turnover_rate=self._float(item, ["换手率", "turnover_rate"]),
                    adj_factor=1.0,
                    limit_up=round(pre_close * 1.1, 2),
                    limit_down=round(pre_close * 0.9, 2),
                    suspend_flag=False,
                    available_date=self._available_date(trade_date, calendar_row),
                    data_version="akshare-%s" % self._compact_date(trade_date),
                ))
        return rows

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        rows = []
        for bar in self.get_daily_bars(start_date, end_date):
            rows.append(ValuationRow(
                trade_date=bar.trade_date,
                code=bar.code,
                pe_ttm=15.0,
                pb=1.5,
                ps_ttm=2.0,
                pcf_ttm=10.0,
                dividend_yield=0.02,
                total_market_value=0.0,
                float_market_value=0.0,
                available_date=bar.available_date,
                data_version="akshare-derived-neutral-%s" % self._compact_date(bar.trade_date),
            ))
        return rows

    def get_financials(self) -> List[FinancialRow]:
        rows = []
        for stock in self.get_stock_basic():
            rows.append(FinancialRow(
                code=stock.code,
                report_period="1990-01-01",
                announce_date="1990-01-01",
                available_date="1990-01-01",
                revenue=1000000000.0,
                net_profit=100000000.0,
                deducted_net_profit=90000000.0,
                operating_cash_flow=120000000.0,
                roe=0.08,
                roa=0.04,
                gross_margin=0.25,
                net_margin=0.10,
                debt_ratio=0.50,
                data_version="akshare-derived-neutral-financial",
            ))
        return rows

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        stocks = self.get_stock_basic()
        rows = []
        for index_code in index_codes:
            normalized_index = index_code.upper()
            if normalized_index not in {"ALL", "FULL_MARKET"}:
                self.warnings.append(
                    "%s index members are temporarily approximated with full-market members." % index_code
                )
            for stock in stocks:
                rows.append(IndexMemberRow(
                    index_code=index_code,
                    code=stock.code,
                    effective_date=trade_date,
                    expire_date=None,
                    data_version=self.data_version,
                ))
        return rows

    def _akshare(self):
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError(AKSHARE_INSTALL_MESSAGE) from exc
        if ak is None:
            raise RuntimeError(AKSHARE_INSTALL_MESSAGE)
        return ak

    def _available_date(self, trade_date: str, calendar_row: Optional[TradeCalendarRow]) -> str:
        if calendar_row and calendar_row.next_trade_date:
            return calendar_row.next_trade_date

        current = date.fromisoformat(trade_date) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()

    def _pre_close(self, item: dict) -> float:
        pre_close = self._pick(item, ["昨收", "pre_close"])
        if pre_close not in (None, ""):
            return self._to_float(pre_close)
        close = self._float(item, ["收盘", "close"])
        pct_change = self._float(item, ["涨跌幅", "pct_chg", "change_pct"])
        if pct_change <= -100:
            return close
        return round(close / (1 + pct_change / 100), 2)

    def _float(self, item: dict, keys: List[str]) -> float:
        return self._to_float(self._pick(item, keys))

    def _to_float(self, value) -> float:
        if value is None or value == "":
            return 0.0
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)

    def _pick(self, item: dict, keys: List[str]):
        for key in keys:
            if key in item:
                return item[key]
        return None

    def _compact_date(self, value: str) -> str:
        return value.replace("-", "")

    def _normalize_date(self, value) -> Optional[str]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        if len(text) == 8 and text.isdigit():
            return "%s-%s-%s" % (text[:4], text[4:6], text[6:])
        return text[:10]

    def _clean_code(self, value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if "." in text:
            text = text.split(".")[0]
        return text.zfill(6)

    def _infer_exchange(self, code: str) -> str:
        if code.startswith(("6", "9")):
            return "SH"
        if code.startswith(("8", "4")):
            return "BJ"
        return "SZ"
