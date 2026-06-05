from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict


class VisionParseService:
    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.model = model

    def account_prompt(self) -> str:
        return (
            "你是证券账户截图解析助手。请从截图中提取账户资金和持仓信息，输出严格 JSON。"
            "需要识别的中文字段包括：总资产、浮动盈亏、当日参考盈亏、总市值、可用、可取、仓位、持仓。"
            "字段包含 broker, account_alias, total_assets, floating_profit, daily_profit, market_value, "
            "available_cash, withdrawable_cash, position_ratio, positions。"
            "positions 每项包含 stock_name, market_value, floating_profit, profit_rate, holding_quantity, "
            "available_quantity, cost_price, current_price。无法识别的字段使用 null，不要编造。"
        )

    def trades_prompt(self) -> str:
        return (
            "你是证券历史成交截图解析助手。请从截图中提取成交记录，输出严格 JSON。"
            "需要识别的中文字段包括：成交时间、成交价格、成交量、成交金额、买入、卖出。"
            "字段包含 date_range 和 trades。trades 每项包含 stock_name, stock_code, side, trade_datetime, "
            "price, quantity, amount。截图中股票代码缺失时 stock_code 使用空字符串，不要猜测代码。"
            "side 只能使用 buy 或 sell。无法识别的字段使用 null，不要编造。"
        )

    def parse_account_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        return self._call_vision(self.account_prompt(), image_bytes, mime_type)

    def parse_trades_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        return self._call_vision(self.trades_prompt(), image_bytes, mime_type)

    def _call_vision(self, prompt: str, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("VISION_API_KEY 未配置，无法使用截图 AI 解析；请使用人工录入或配置视觉模型。")
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.api_base}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"视觉解析请求失败：HTTP {exc.code} {detail}") from exc
        content = response_payload["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return json.loads(content)
        raise RuntimeError("视觉解析响应格式异常")
