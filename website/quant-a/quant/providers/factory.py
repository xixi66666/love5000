"""Provider 工厂 `create_provider`。

按 `configs/app.yaml` 的 `provider.active` 构造数据源实现：`mock`（确定性假数据，
测试与离线演示用）、`akshare`（默认，真实行情 + 中性估值占位）、`tushare`（需要
`TUSHARE_TOKEN` 与相应接口权限）。AkShare/Tushare 的 import 放在分支内延迟执行，
未安装它们时 `mock` 路径仍可正常工作。
"""

from typing import Any, Dict, Optional

from quant.providers.base import DataProvider
from quant.providers.mock_provider import MockProvider


def create_provider(config: Optional[Dict[str, Any]] = None) -> DataProvider:
    """根据配置创建 Provider 实例。

    Args:
        config: 完整应用配置（`load_app_config()` 的返回值）；为空时按缺少 `provider`
            段处理，等价于选择 `mock`。

    Returns:
        实现 `DataProvider` 协议的实例。`akshare`/`tushare` 的构造函数只读取超时与
        token 环境变量名，不会在创建时发起网络请求。

    Raises:
        ValueError: `provider.active` 不是 `mock`/`akshare`/`tushare` 之一。
    """
    provider_config = (config or {}).get("provider", {})
    active = provider_config.get("active", "mock")

    if active == "mock":
        return MockProvider()

    if active == "akshare":
        akshare_config = provider_config.get("akshare", {})
        from quant.providers.akshare_provider import AkShareProvider

        return AkShareProvider(timeout_seconds=akshare_config.get("timeout_seconds", 15))

    if active == "tushare":
        tushare_config = provider_config.get("tushare", {})
        from quant.providers.tushare_provider import TushareProvider

        return TushareProvider(
            token_env=tushare_config.get("token_env", "TUSHARE_TOKEN"),
            timeout_seconds=tushare_config.get("timeout_seconds", 15),
        )

    raise ValueError("Unsupported provider: {}".format(active))
