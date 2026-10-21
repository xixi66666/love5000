"""异步工作台适配公共模型客户端。"""
from . import _model_routing as routing

_client = routing.ServiceModelClient("scrapling-ui")
try_chat = _client.try_chat_async
native_chat = routing.native_chat_async
