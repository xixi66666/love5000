"""仅绑定文本模型入口，语音和视频使用专用客户端。"""
from . import _model_routing as routing

_client = routing.ServiceModelClient("skill-finder")
try_chat = _client.try_chat_async
native_chat = routing.native_chat_async
ModelProviderError = routing.ModelProviderError
