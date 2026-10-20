"""仅文本生成接入全局模型，不影响语音与视频模型。"""
import asyncio
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[4] / "model-routing/model_routing.py"
_routing = None
if _path.is_file():
    _spec = importlib.util.spec_from_file_location("love530_model_routing", _path)
    _routing = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_routing)


async def active():
    return _routing is not None and await asyncio.to_thread(_routing.active, "skill-finder")


async def chat(payload):
    return await asyncio.to_thread(_routing.chat, "skill-finder", payload)
