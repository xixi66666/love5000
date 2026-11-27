"""风险与偏差披露 `RiskService`。

`known_biases()` 返回的是当前量化流程**已知**的方法论偏差清单（人工维护的固定内容），
不是根据数据算出来的风险指标。它是报告必须携带的免责边界：说明 mock 数据只用于验证
流程、回测按开盘价加固定滑点成交而没有分钟级 VWAP。Provider 或执行模型变化时，
这份清单需要同步更新，否则报告会漏掉真实偏差。
"""

from typing import Dict, List


class RiskService:
    """提供固定的已知偏差清单。"""

    def known_biases(self) -> List[Dict[str, str]]:
        """返回固定偏差清单。

        Returns:
            每项含 `bias_type`、`severity`、`affected_period`、`affected_fields`、
            `impact_description`、`mitigation`。第一条覆盖 mock 数据区间
            （2024-01-02 至 2024-03-31）的数据源偏差，第二条覆盖全部回测日的
            成交价偏差；文案面向报告读者，不构成投资建议。
        """
        return [
            {
                "bias_type": "data_source",
                "severity": "medium",
                "affected_period": "2024-01-02 to 2024-03-31",
                "affected_fields": "mock market, valuation, financial",
                "impact_description": "Mock data validates the pipeline but does not represent real market behavior.",
                "mitigation": "Use production Provider and data quality checks before interpreting performance.",
            },
            {
                "bias_type": "execution_price",
                "severity": "medium",
                "affected_period": "all backtest dates",
                "affected_fields": "open price, slippage",
                "impact_description": "The first backtest uses open price plus fixed slippage rather than minute VWAP.",
                "mitigation": "Disclose the assumption and add VWAP data in a later execution model.",
            },
        ]
