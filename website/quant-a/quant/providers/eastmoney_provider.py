from typing import List

import requests

from quant.providers.base import DailyBarRow


class EastmoneyProvider:
    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def _get_json(self, url: str, params: dict) -> dict:
        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        raise NotImplementedError("Eastmoney daily bar parsing is implemented after mock pipeline is stable.")
