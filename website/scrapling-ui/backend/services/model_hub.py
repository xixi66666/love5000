"""加载公共文本模型路由。"""
import asyncio
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "model-routing/model_routing.py"
_routing = None
if _path.is_file():
    _spec = importlib.util.spec_from_file_location("love530_model_routing", _path)
    _routing = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_routing)


async def active():
    return _routing is not None and await asyncio.to_thread(_routing.active, "scrapling-ui")


async def chat(payload):
    return await asyncio.to_thread(_routing.chat, "scrapling-ui", payload)
