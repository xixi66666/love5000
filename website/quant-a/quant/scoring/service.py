from typing import Dict, List


class ScoringService:
    def __init__(self, value_weight: float = 0.30, quality_weight: float = 0.35, momentum_weight: float = 0.25):
        self.value_weight = value_weight
        self.quality_weight = quality_weight
        self.momentum_weight = momentum_weight

    def score(
        self,
        trade_date: str,
        factors: List[Dict[str, object]],
        data_version: str,
        model_version: str,
    ) -> List[Dict[str, object]]:
        scored = []
        for row in factors:
            total = (
                float(row["value_score"]) * self.value_weight
                + float(row["quality_score"]) * self.quality_weight
                + float(row["momentum_score"]) * self.momentum_weight
                - float(row["risk_penalty"])
            )
            scored.append({
                "trade_date": trade_date,
                "code": row["code"],
                "name": row["name"],
                "industry": row["industry"],
                "value_score": round(float(row["value_score"]), 4),
                "quality_score": round(float(row["quality_score"]), 4),
                "momentum_score": round(float(row["momentum_score"]), 4),
                "risk_penalty": round(float(row["risk_penalty"]), 4),
                "liquidity_flag": row["liquidity_flag"],
                "total_score": round(total, 4),
                "rank": 0,
                "factor_raw_values": row["factor_raw_values"],
                "factor_scores": {
                    "value": row["value_score"],
                    "quality": row["quality_score"],
                    "momentum": row["momentum_score"],
                },
                "missing_fields": row["missing_fields"],
                "risk_flags": row["risk_flags"],
                "data_version": data_version,
                "model_version": model_version,
            })
        scored.sort(key=lambda item: item["total_score"], reverse=True)
        for index, item in enumerate(scored, start=1):
            item["rank"] = index
        return scored
