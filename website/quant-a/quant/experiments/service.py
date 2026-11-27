"""实验元数据服务 `ExperimentService`。

只生成实验编号与三个版本号（模型、数据、配置）的快照，用于把一次评分或回测结果
绑定到可复现的输入版本。这里不读取行情、不计算指标，也不产生买卖结论：
`decision` 固定为 `watch_only`（仅观察），保持非投资建议边界。
"""

from datetime import datetime
from typing import Dict
from uuid import uuid4


class ExperimentService:
    """生成带版本快照的实验记录。"""

    def create_experiment(self, model_version: str, data_version: str, config_version: str) -> Dict[str, str]:
        """创建一条实验记录（纯内存，不落库）。

        Args:
            model_version: 模型版本，来自 `configs/model_v0_1.yaml` 的 `model.version`。
            data_version: 数据版本，来自 Provider 或 `data_versions` 表最新记录。
            config_version: 配置版本，来自 `configs/app.yaml` 的 `versions.config_version`。

        Returns:
            `experiment_id`（`exp-` 前缀 + 12 位十六进制）、秒级 UTC 时间戳
            （手工追加 `Z` 后缀）、三个版本字段，以及固定为 `watch_only` 的 `decision`。
        """
        return {
            "experiment_id": f"exp-{uuid4().hex[:12]}",
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_version": model_version,
            "data_version": data_version,
            "config_version": config_version,
            "decision": "watch_only",
        }
