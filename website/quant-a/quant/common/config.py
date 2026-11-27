"""quant-a 的 YAML 配置读取入口。

配置文件固定放在 `website/quant-a/configs/`（`app.yaml`、`universe.yaml`、
`model_v0_1.yaml`、`cost_model.yaml`），不读取环境变量覆盖，也不做缓存：每次调用
都重新读盘，改完配置后下一次请求即可生效。读取失败（文件缺失、YAML 语法错误）
直接向上抛出，由调用方决定降级或返回错误。

返回值统一是 YAML 顶层映射，调用方按 `config["section"]["key"]` 取值；空文件返回
空字典，因此缺失的键会在取值处暴露为 `KeyError` 而不是 `None` 传播。
"""

from pathlib import Path
from typing import Any, Dict

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "configs"


def load_yaml(name: str) -> Dict[str, Any]:
    """读取 `configs/` 下的一个 YAML 文件。

    Args:
        name: 配置文件名（含扩展名），相对 `configs/` 目录，例如 `app.yaml`。

    Returns:
        YAML 顶层映射；文件为空或只含注释时返回空字典，便于调用方写默认值。

    Raises:
        FileNotFoundError: 配置文件不存在。
        yaml.YAMLError: YAML 语法错误，不做静默兜底。
    """
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_app_config() -> Dict[str, Any]:
    """读取 `app.yaml`：应用名/端口、Provider 选择与超时、DuckDB 路径、版本号。"""
    return load_yaml("app.yaml")


def load_universe_config() -> Dict[str, Any]:
    """读取 `universe.yaml`：指数池，以及上市天数、20 日均额、ST、停牌的过滤阈值。"""
    return load_yaml("universe.yaml")


def load_model_config() -> Dict[str, Any]:
    """读取 `model_v0_1.yaml`：因子权重、风险扣分上限、`top_n` 与单票权重上限。"""
    return load_yaml("model_v0_1.yaml")


def load_cost_config() -> Dict[str, Any]:
    """读取 `cost_model.yaml`：佣金、最低佣金、印花税、过户费与滑点假设。

    目前回测服务未读取该文件，交易成本以常量写死在 `BacktestService` 中；
    修改这里的费率不会自动改变回测结果。
    """
    return load_yaml("cost_model.yaml")
