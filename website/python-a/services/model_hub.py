"""绑定服务标识；部署副本由 scripts/sync-model-routing.py 生成。"""
from . import _model_routing as routing

_client = routing.ServiceModelClient("python-a")
try_chat = _client.try_chat
native_chat = routing.native_chat
