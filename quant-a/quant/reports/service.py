from typing import Dict

from quant.risk.service import RiskService


class ReportService:
    def __init__(self, risk_service: RiskService):
        self.risk_service = risk_service

    def build_report(self, experiment_id: str, backtest_result: Dict[str, object]) -> Dict[str, object]:
        nav = backtest_result["nav"]
        nav_values = [float(item["nav"]) for item in nav]
        peak = nav_values[0] if nav_values else 1.0
        max_drawdown = 0.0
        for value in nav_values:
            peak = max(peak, value)
            max_drawdown = min(max_drawdown, value / peak - 1.0)

        return {
            "experiment_id": experiment_id,
            "metrics": {
                "start_nav": nav_values[0] if nav_values else 1.0,
                "end_nav": nav_values[-1] if nav_values else 1.0,
                "total_return": round((nav_values[-1] - 1.0) if nav_values else 0.0, 6),
                "max_drawdown": round(max_drawdown, 6),
                "order_count": len(backtest_result["orders"]),
            },
            "nav": nav,
            "orders": backtest_result["orders"],
            "known_biases": self.risk_service.known_biases(),
        }
