"""组合构建服务 `PortfolioService`。

把评分结果转成等权目标持仓。权重是 0~1 的小数（不是百分比），并做单票上限截断：
当入选数量少于 `1 / single_stock_weight_limit`（默认上限 5%，即 20 只）时，权重之和
小于 1，剩余部分保留为现金，不做二次归一化。这是刻意的保守处理——少量标的不会被
被动放大到高风险仓位，回测也因此宁可留现金也不满仓。
"""

from typing import Dict, List


class PortfolioService:
    """按排名截取前 `top_n` 只并给出等权目标权重。"""

    def __init__(self, top_n: int = 30, single_stock_weight_limit: float = 0.05):
        """设置组合规模与单票上限。

        Args:
            top_n: 入选股票数，默认 30，对应 `configs/model_v0_1.yaml` 的 `model.top_n`。
            single_stock_weight_limit: 单票权重上限，0~1 小数，默认 0.05 即 5%。
        """
        self.top_n = top_n
        self.single_stock_weight_limit = single_stock_weight_limit

    def build_targets(self, scores: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """由评分列表生成目标持仓。

        Args:
            scores: 评分行序列，调用方需已按排名排好序（本方法不再排序，只按传入顺序
                截取前 `top_n` 条）。

        Returns:
            目标持仓列表，每项含 `code`/`name`/`industry`/`target_weight`/`rank`/
            `total_score`；`target_weight = min(1/n, 单票上限)`。空输入返回空列表，
            上层的"清仓"路径因此可以安全走空组合。
        """
        selected = scores[: self.top_n]
        if not selected:
            return []

        equal_weight = min(1.0 / len(selected), self.single_stock_weight_limit)
        return [
            {
                "code": item["code"],
                "name": item["name"],
                "industry": item["industry"],
                "target_weight": equal_weight,
                "rank": item["rank"],
                "total_score": item["total_score"],
            }
            for item in selected
        ]
