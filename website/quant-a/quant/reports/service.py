"""回测报告组装 `ReportService`。

把回测的净值曲线与成交明细整理成一份可展示的报告：起始/结束净值、累计收益、最大回撤、
成交笔数，并附上 `RiskService` 的已知偏差清单。口径：净值以 1.0 为初始基数，
`total_return` 与 `max_drawdown` 都是小数（`-0.12` 表示回撤 12%），不是百分比。
报告只描述历史模拟结果，不预测未来收益，也不给出买入/卖出结论。
"""

from typing import Dict

from quant.risk.service import RiskService


class ReportService:
    """基于回测结果生成指标与偏差披露。"""

    def __init__(self, risk_service: RiskService):
        """注入风险披露服务。

        Args:
            risk_service: 提供 `known_biases()` 的实例；报告必须携带该清单。
        """
        self.risk_service = risk_service

    def build_report(self, experiment_id: str, backtest_result: Dict[str, object]) -> Dict[str, object]:
        """计算并返回报告字典。

        最大回撤用净值序列逐点比较历史峰值得到，峰值初始取序列首值，因此结果必然
        小于等于 0；空净值序列时回退为 1.0 与 0 收益，不抛异常。

        Args:
            experiment_id: 回测实验编号，原样透传。
            backtest_result: `BacktestService.run` 的返回值，至少含 `nav`（每项带
                `nav` 字段）与 `orders`。

        Returns:
            含 `experiment_id`、`metrics`、原始 `nav`/`orders` 与 `known_biases` 的字典。

        Raises:
            KeyError: `backtest_result` 缺少 `nav` 或 `orders` 键时由下标访问抛出。
        """
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
