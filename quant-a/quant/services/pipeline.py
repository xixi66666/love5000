from pathlib import Path
from typing import Dict, List, Optional

from quant.providers.base import DataProvider
from quant.providers.mock_provider import MockProvider
from quant.storage.repository import QuantRepository


class QuantPipeline:
    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[DataProvider] = None):
        self.repository = repository or QuantRepository(Path("data/quant.duckdb"))
        self.provider = provider or MockProvider()

    def sync_data(self, start_date: str, end_date: str, index_codes: List[str]) -> Dict[str, object]:
        calendar = self.provider.get_trade_calendar(start_date, end_date)
        stocks = self.provider.get_stock_basic()
        daily_bars = self.provider.get_daily_bars(start_date, end_date)
        valuations = self.provider.get_valuation(start_date, end_date)
        financials = self.provider.get_financials()
        members = self.provider.get_index_members(index_codes, end_date)
        data_version = self.provider.data_version

        counts = {
            "calendar_count": self.repository.replace_table("trade_calendar", calendar),
            "stock_count": self.repository.replace_table("stock_basic", stocks),
            "daily_bar_count": self.repository.replace_table("daily_bar", daily_bars),
            "valuation_count": self.repository.replace_table("valuation", valuations),
            "financial_count": self.repository.replace_table("financial", financials),
            "index_member_count": self.repository.replace_table("index_member", members),
        }
        self.repository.record_data_version(data_version, "mock", start_date, end_date)
        return {
            "data_version": data_version,
            **counts,
        }
