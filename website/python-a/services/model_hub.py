"""加载仓库内公共路由；独立部署时保留原服务能力。"""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "model-routing/model_routing.py"
_routing = None
if _path.is_file():
    _spec = importlib.util.spec_from_file_location("love530_model_routing", _path)
    _routing = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_routing)


def active():
    return _routing is not None and _routing.active("python-a")


def chat(payload):
    return _routing.chat("python-a", payload)
