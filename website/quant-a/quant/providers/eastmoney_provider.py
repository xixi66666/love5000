"""东方财富行情占位 Provider `EastmoneyProvider`。

目前只搭好带超时的 JSON 请求骨架，日线解析尚未实现（`get_daily_bars` 直接抛
`NotImplementedError`），因此 `configs/app.yaml` 里没有 `eastmoney` 这个 active 选项，
`create_provider` 也不会构造它。真正在 AkShare 失败时兜底的东方财富 K 线逻辑写在
`AkShareProvider._eastmoney_daily_bars` 中。
"""

from typing import List

import requests

from quant.providers.base import DailyBarRow


class EastmoneyProvider:
    """东方财富行情接入的最小骨架。"""

    def __init__(self, timeout_seconds: int = 10):
        """构造提供方并记录超时。

        Args:
            timeout_seconds: 单次 HTTP 请求超时秒数；上游卡顿时以超时失败而不是无限等待。
        """
        self.timeout_seconds = timeout_seconds

    def _get_json(self, url: str, params: dict) -> dict:
        """发起带超时的 GET 并解析 JSON。

        Args:
            url: 完整接口地址。
            params: 查询参数。

        Returns:
            解析后的 JSON 对象。

        Raises:
            requests.RequestException: 连接失败、超时或非 2xx 状态（`raise_for_status`）。
            ValueError: 响应体不是合法 JSON。
        """
        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        """未实现：日线解析等 mock 流水线稳定后再补。

        Raises:
            NotImplementedError: 总是抛出，调用方需走 AkShare 的兜底链路。
        """
        raise NotImplementedError("Eastmoney daily bar parsing is implemented after mock pipeline is stable.")
