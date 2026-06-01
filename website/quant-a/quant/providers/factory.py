from typing import Any, Dict, Optional

from quant.providers.base import DataProvider
from quant.providers.mock_provider import MockProvider


def create_provider(config: Optional[Dict[str, Any]] = None) -> DataProvider:
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
