"""多因子评分 `ScoringService`。

把因子引擎给出的价值/质量/动量三个维度分（0~100 的百分位，100 表示该维度最优）
按权重合成总分：`总分 = 价值*0.30 + 质量*0.35 + 动量*0.25 - 风险扣分`。默认权重之和
为 0.90、风险扣分上限 10 分，因此总分理论上限约 90 分、下限 -10 分；分数只用于横向
排序，不代表预期收益率，也不构成买入建议。排名按总分降序，`rank=1` 为最高分。
"""

from typing import Dict, List


class ScoringService:
    """按固定权重合成分数并给出排名。"""

    def __init__(self, value_weight: float = 0.30, quality_weight: float = 0.35, momentum_weight: float = 0.25):
        """设置三个维度的权重。

        注意：`QuantPipeline.run_scores` 目前用默认参数构造本服务，`model_v0_1.yaml`
        的 `model.weights` 不会被读入；调整权重需要同时修改这里和配置文件，否则
        页面展示的配置与实际计算不一致。

        Args:
            value_weight: 价值维度权重，0~1 小数。
            quality_weight: 质量维度权重，0~1 小数。
            momentum_weight: 动量维度权重，0~1 小数。
        """
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
        """对因子结果打分并按总分降序排名。

        Args:
            trade_date: 评分交易日（ISO 日期），原样写入每条结果用于回溯。
            factors: `FactorEngine.calculate` 的输出，每行需含 `value_score`、
                `quality_score`、`momentum_score`、`risk_penalty`、`liquidity_flag`、
                `factor_raw_values`、`missing_fields`、`risk_flags`。
            data_version: 数据版本号，写入结果便于复现。
            model_version: 模型版本号，写入结果便于复现。

        Returns:
            评分行列表（已按总分降序、`rank` 从 1 开始），维度分与总分保留 4 位小数，
            另附 `factor_scores` 便于前端直接画三维对比。

        Raises:
            KeyError: 因子行缺少必需字段时由字典下标访问抛出，避免用默认 0 分掩盖缺数据。
        """
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
