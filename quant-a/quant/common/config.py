from pathlib import Path
from typing import Any, Dict

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "configs"


def load_yaml(name: str) -> Dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_app_config() -> Dict[str, Any]:
    return load_yaml("app.yaml")


def load_universe_config() -> Dict[str, Any]:
    return load_yaml("universe.yaml")


def load_model_config() -> Dict[str, Any]:
    return load_yaml("model_v0_1.yaml")


def load_cost_config() -> Dict[str, Any]:
    return load_yaml("cost_model.yaml")
