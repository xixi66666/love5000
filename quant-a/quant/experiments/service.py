from datetime import datetime
from typing import Dict
from uuid import uuid4


class ExperimentService:
    def create_experiment(self, model_version: str, data_version: str, config_version: str) -> Dict[str, str]:
        return {
            "experiment_id": f"exp-{uuid4().hex[:12]}",
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_version": model_version,
            "data_version": data_version,
            "config_version": config_version,
            "decision": "watch_only",
        }
