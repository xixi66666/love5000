from typing import List, Optional

from quant.providers.akshare_provider import AkShareProvider
from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)
from quant.providers.tushare_provider import TushareProvider


class TushareAkshareProvider:
    """Tushare-first provider with AkShare fallback for stock basics and daily bars."""

    name = "tushare_akshare"

    def __init__(self, primary=None, fallback=None):
        self.primary = primary or TushareProvider()
        self.fallback = fallback or AkShareProvider()
        self.fallback_count = 0
        self.failed_code_count = 0
        self.failed_codes = []
        self.warnings = []

    @property
    def data_version(self) -> str:
        primary_version = getattr(self.primary, "data_version", "tushare")
        fallback_version = getattr(self.fallback, "data_version", "akshare")
        return f"{primary_version}+{fallback_version}"

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        try:
            return self.primary.get_trade_calendar(start_date, end_date)
        except Exception as exc:
            self._record_warning("akshare", "trade_calendar", f"fallback after Tushare failure: {exc}")
            return self.fallback.get_trade_calendar(start_date, end_date)

    def get_stock_basic(self) -> List[StockBasicRow]:
        try:
            rows = self.primary.get_stock_basic()
        except Exception:
            rows = []
        if rows:
            return rows
        fallback_rows = self.fallback.get_stock_basic()
        self.fallback_count += len(fallback_rows)
        return fallback_rows

    def get_daily_bars(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[List[str]] = None,
    ) -> List[DailyBarRow]:
        self.failed_codes = []
        self.failed_code_count = 0
        if not codes:
            try:
                return self._primary_daily_bars(start_date, end_date, None)
            except Exception:
                fallback_rows = self.fallback.get_daily_bars(start_date, end_date, codes=None)
                self.fallback_count += len({row.code for row in fallback_rows})
                return fallback_rows

        try:
            rows = self._primary_daily_bars(start_date, end_date, codes)
        except Exception:
            rows = []

        primary_codes = {row.code for row in rows}
        for code in codes:
            if code in primary_codes:
                continue

            fallback_rows = self.fallback.get_daily_bars(start_date, end_date, codes=[code])
            if fallback_rows:
                self.fallback_count += 1
                rows.extend(fallback_rows)
            else:
                self.failed_codes.append(code)

        self.failed_code_count = len(self.failed_codes)
        return rows

    def _primary_daily_bars(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[List[str]],
    ) -> List[DailyBarRow]:
        try:
            return self.primary.get_daily_bars(start_date, end_date, codes=codes)
        except TypeError:
            rows = self.primary.get_daily_bars(start_date, end_date)
            if not codes:
                return rows
            code_set = set(codes)
            return [row for row in rows if row.code in code_set]

    def get_valuation(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[List[str]] = None,
    ) -> List[ValuationRow]:
        try:
            return self.primary.get_valuation(start_date, end_date, codes=codes)
        except TypeError:
            try:
                rows = self.primary.get_valuation(start_date, end_date)
                if not codes:
                    return rows
                code_set = set(codes)
                return [row for row in rows if row.code in code_set]
            except Exception as exc:
                self._record_warning("tushare", "valuation", str(exc))
                return []
        except Exception as exc:
            self._record_warning("tushare", "valuation", str(exc))
            return []

    def get_financials(self) -> List[FinancialRow]:
        try:
            return self.primary.get_financials()
        except Exception as exc:
            self._record_warning("tushare", "financial", str(exc))
            return []

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        if any(code.upper() in {"ALL", "FULL_MARKET"} for code in index_codes):
            data_version = self.data_version
            rows = []
            for index_code in index_codes:
                if index_code.upper() not in {"ALL", "FULL_MARKET"}:
                    continue
                for stock in self.get_stock_basic():
                    rows.append(IndexMemberRow(index_code, stock.code, trade_date, None, data_version))
            return rows
        return self.primary.get_index_members(index_codes, trade_date)

    def _record_warning(self, source: str, dataset: str, message: str) -> None:
        warning = {
            "source": source,
            "dataset": dataset,
            "message": message,
        }
        if warning not in self.warnings:
            self.warnings.append(warning)
