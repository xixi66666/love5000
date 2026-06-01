from typing import Dict, List


class PortfolioService:
    def __init__(self, top_n: int = 30, single_stock_weight_limit: float = 0.05):
        self.top_n = top_n
        self.single_stock_weight_limit = single_stock_weight_limit

    def build_targets(self, scores: List[Dict[str, object]]) -> List[Dict[str, object]]:
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
