"""证券账户与历史成交截图的视觉模型解析。

对外提供 ``VisionParseService``：``account_prompt`` / ``trades_prompt`` 给出两组
中文提示词，``parse_account_screenshot`` / ``parse_trades_screenshot`` 把截图转成
结构化字典。请求走 OpenAI 兼容的 ``{api_base}/chat/completions``，并强制
``response_format=json_object``，让模型只输出 JSON。

数据来源：``api_base`` / ``api_key`` / ``model`` 由 ``server.py`` 从仓库根目录
``model.properties`` 的 ``vision.*`` 注入，本模块不读取任何环境变量，也不读取旧版
``deepseek.local.json``。

持久化：本模块不写磁盘。解析结果由调用方包装成解析草稿，经
``TradeService.create_parse_draft`` 落到 ``parse_drafts.json``，用户在页面上确认后
才写入 ``trades.json`` / ``account_snapshots.json``。

降级策略：未配置密钥时抛 ``ValueError`` 并给出可操作的中文提示（改人工录入）；
上游 HTTP 错误把状态码与响应正文一起抛出以便排查；请求超时设为 90 秒，因为截图
经 base64 编码后请求体较大。HTTP 处理器负责把这些异常转成 ``success=false``，
页面因此可以继续使用人工录入通道。
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict


class VisionParseService:
    """把证券 App 截图交给视觉模型并返回结构化 JSON。

    实例只保存不可变的配置，可被多个请求线程共享；提示词每次调用现拼，不含状态。
    """

    def __init__(self, api_key: str, api_base: str, model: str):
        """保存视觉模型连接参数并做最小规范化。

        Args:
            api_key: ``vision.api-key`` 的原文，两端空白会被去掉；为空表示未配置，
                真正的报错延后到 ``_call_vision``，便于服务先启动再补配置。
            api_base: OpenAI 兼容基址，末尾斜杠会被去掉，请求时再拼
                ``/chat/completions``。
            model: 视觉模型名，直接透传给上游。
        """
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.model = model

    def account_prompt(self) -> str:
        """返回账户截图解析提示词。

        提示词把可识别的中文字段（总资产、浮动盈亏、当日参考盈亏、总市值、可用、
        可取、仓位、持仓）逐一映射到英文字段，并要求无法识别的字段给 ``null``、
        不得编造——资金数字编造的代价高于缺字段，页面上缺失值可以人工补。

        Returns:
            可直接放进 ``messages[0].content[0].text`` 的中文提示词。
        """
        return (
            "你是证券账户截图解析助手。请从截图中提取账户资金和持仓信息，输出严格 JSON。"
            "需要识别的中文字段包括：总资产、浮动盈亏、当日参考盈亏、总市值、可用、可取、仓位、持仓。"
            "字段包含 broker, account_alias, total_assets, floating_profit, daily_profit, market_value, "
            "available_cash, withdrawable_cash, position_ratio, positions。"
            "positions 每项包含 stock_name, market_value, floating_profit, profit_rate, holding_quantity, "
            "available_quantity, cost_price, current_price。无法识别的字段使用 null，不要编造。"
        )

    def trades_prompt(self) -> str:
        """返回历史成交截图解析提示词。

        除字段映射外还约束了两条业务规则：截图中没有股票代码时 ``stock_code``
        用空串而不是猜代码，``side`` 只允许 ``buy`` / ``sell``，与
        ``TradeService._normalize_side`` 的白名单保持一致。

        Returns:
            可直接放进 ``messages[0].content[0].text`` 的中文提示词。
        """
        return (
            "你是证券历史成交截图解析助手。请从截图中提取成交记录，输出严格 JSON。"
            "需要识别的中文字段包括：成交时间、成交价格、成交量、成交金额、买入、卖出。"
            "字段包含 date_range 和 trades。trades 每项包含 stock_name, stock_code, side, trade_datetime, "
            "price, quantity, amount。截图中股票代码缺失时 stock_code 使用空字符串，不要猜测代码。"
            "side 只能使用 buy 或 sell。无法识别的字段使用 null，不要编造。"
        )

    def parse_account_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """解析账户总览截图。

        Args:
            image_bytes: 上传文件的原始字节，本层不校验大小与格式。
            mime_type: 图片 MIME，例如 ``image/png``，用于拼 data URL。

        Returns:
            模型给出的账户字段字典；缺字段的键为 ``None``。

        Raises:
            ValueError: 视觉模型密钥未配置。
            RuntimeError: 上游 HTTP 失败或返回结构异常。
        """
        return self._call_vision(self.account_prompt(), image_bytes, mime_type)

    def parse_trades_screenshot(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """解析历史成交列表截图，返回 ``{date_range, trades}`` 形态的字典。

        Args:
            image_bytes: 上传文件的原始字节。
            mime_type: 图片 MIME，例如 ``image/jpeg``。

        Returns:
            含 ``trades`` 数组的字典，每项字段由 ``trades_prompt`` 约定。

        Raises:
            ValueError: 视觉模型密钥未配置。
            RuntimeError: 上游 HTTP 失败或返回结构异常。
        """
        return self._call_vision(self.trades_prompt(), image_bytes, mime_type)

    def _call_vision(self, prompt: str, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """把提示词与 base64 图片组合成一次 chat/completions 请求。

        ``temperature`` 压到 0.1 并开启 JSON 模式，尽量让同类截图输出稳定；
        90 秒超时覆盖手机截图经 base64 放大后的上传与推理时间。上游返回的
        ``content`` 只有字符串形态会被解析，其他结构一律当作响应异常。

        Args:
            prompt: ``account_prompt`` 或 ``trades_prompt`` 的结果。
            image_bytes: 图片原始字节，编码后放进 data URL。
            mime_type: 图片 MIME。

        Raises:
            ValueError: 未配置 ``vision.api-key``，提示中指向 model.properties 与人工录入。
            RuntimeError: 上游 HTTP 非 2xx（带状态码与正文），或 ``content`` 不是字符串。
            KeyError: 上游返回的不是标准 chat.completion 结构时会直接冒泡，
                此时不伪装成“解析失败”，便于区分配置问题与模型问题。
        """
        if not self.api_key:
            raise ValueError("视觉模型未配置，无法使用截图 AI 解析；请在项目根目录 model.properties 填写 vision.api-key，或使用人工录入。")
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
