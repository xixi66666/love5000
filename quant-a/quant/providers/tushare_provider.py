import importlib
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


class TushareProvider:
    name = "tushare"
    data_version = "tushare-v1"

    def __init__(self, timeout_seconds: int = 15, token_env: str = "TUSHARE_TOKEN"):
        self.timeout_seconds = timeout_seconds
        self.token_env = token_env
        self.token = os.environ.get(token_env, "").strip()
        self._pro = None

    def get_stock_basic(self) -> List[StockBasicRow]:
        rows = self._to_records(self._pro_api().stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,exchange,list_date,delist_date,list_status,industry",
        ))
        return [
            StockBasicRow(
                code=self._stock_code(row.get("ts_code")),
                name=self._text(row.get("name")),
                exchange=self._text(row.get("exchange")),
                list_date=self._format_date(row.get("list_date")),
                delist_date=self._optional_date(row.get("delist_date")),
                status=self._map_status(row.get("list_status")),
                industry=self._text(row.get("industry")),
                is_st="ST" in self._text(row.get("name")).upper(),
            )
            for row in rows
        ]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        records = self._to_records(self._pro_api().trade_cal(
            exchange="",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        open_days = [row for row in records if int(row.get("is_open") or 0) == 1]
        open_days.sort(key=lambda item: self._compact_date(item.get("cal_date")))

        rows = []
        for index, row in enumerate(open_days):
            trade_date = self._format_date(row.get("cal_date"))
            next_trade_date = self._format_date(open_days[index + 1].get("cal_date")) if index + 1 < len(open_days) else None
            rows.append(TradeCalendarRow(
                trade_date=trade_date,
                is_open=True,
                prev_trade_date=self._optional_date(row.get("pretrade_date")),
                next_trade_date=next_trade_date,
                is_month_end=next_trade_date is None or next_trade_date[:7] != trade_date[:7],
            ))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        rows = self._to_records(self._pro_api().daily(
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        return [
            DailyBarRow(
                trade_date=self._format_date(row.get("trade_date")),
                code=self._stock_code(row.get("ts_code")),
                open=self._float(row.get("open")),
                high=self._float(row.get("high")),
                low=self._float(row.get("low")),
                close=self._float(row.get("close")),
                pre_close=self._float(row.get("pre_close")),
                volume=self._float(row.get("vol")),
                amount=self._float(row.get("amount")),
                turnover_rate=0.0,
                adj_factor=1.0,
                limit_up=0.0,
                limit_down=0.0,
                suspend_flag=False,
                available_date=self._next_business_date(row.get("trade_date")),
                data_version=self.data_version,
            )
            for row in rows
        ]

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        rows = self._to_records(self._pro_api().daily_basic(
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        return [
            ValuationRow(
                trade_date=self._format_date(row.get("trade_date")),
                code=self._stock_code(row.get("ts_code")),
                pe_ttm=self._float(row.get("pe_ttm")),
                pb=self._float(row.get("pb")),
                ps_ttm=self._float(row.get("ps_ttm")),
                pcf_ttm=self._float(row.get("pcf_ttm", row.get("pcf"))),
                dividend_yield=self._float(row.get("dv_ttm")),
                total_market_value=self._float(row.get("total_mv")),
                float_market_value=self._float(row.get("circ_mv")),
                available_date=self._next_business_date(row.get("trade_date")),
                data_version=self.data_version,
            )
            for row in rows
        ]

    def get_financials(self) -> List[FinancialRow]:
        raise NotImplementedError(
            "Tushare financial endpoints require matching Tushare permissions; "
            "extend this provider with income, balancesheet, cashflow and fina_indicator mappings when the token scope is available."
        )

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        raise NotImplementedError(
            "Tushare index member endpoints require matching Tushare permissions; "
            "extend this provider with index_weight or index_basic mappings when the token scope is available."
        )

    def _pro_api(self):
        if not self.token:
            raise RuntimeError("Tushare token is required. Set TUSHARE_TOKEN before using provider.active=tushare.")
        if self._pro is None:
            try:
                tushare = importlib.import_module("tushare")
            except ImportError as exc:
                raise RuntimeError("Tushare is not installed. Run: python -m pip install -r requirements.txt") from exc
            self._pro = tushare.pro_api(self.token)
        return self._pro

    def _to_records(self, data: Any) -> List[Dict[str, Any]]:
        if data is None:
            return []
        if hasattr(data, "to_dict"):
            return data.to_dict(orient="records")
        return list(data)

    def _compact_date(self, value: Any) -> str:
        text = self._text(value)
        return text.replace("-", "")

    def _format_date(self, value: Any) -> str:
        text = self._compact_date(value)
        if not text:
            return ""
        return "{}-{}-{}".format(text[:4], text[4:6], text[6:8])

    def _optional_date(self, value: Any) -> Optional[str]:
        text = self._text(value)
        if not text:
            return None
        return self._format_date(text)

    def _next_business_date(self, value: Any) -> str:
        current = date.fromisoformat(self._format_date(value)) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()

    def _stock_code(self, ts_code: Any) -> str:
        return self._text(ts_code).split(".")[0]

    def _map_status(self, value: Any) -> str:
        status = self._text(value)
        return {
            "L": "listed",
            "D": "delisted",
            "P": "paused",
        }.get(status, status)

    def _float(self, value: Any) -> float:
        if value is None or value == "":
            return 0.0
        return float(value)

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
