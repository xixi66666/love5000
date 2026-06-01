from typing import Dict, List


class RiskService:
    def known_biases(self) -> List[Dict[str, str]]:
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
