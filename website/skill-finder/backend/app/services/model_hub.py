"""仅绑定文本模型入口，语音和视频使用专用客户端。

把共享的模型路由副本（同目录的 ``_model_routing``，由 ``scripts/sync-model-routing.py``
同步，不要手改）收敛成三个名字：``try_chat`` 走“跟随主页统一模型”的路由，
未选择模型时返回 ``None``，调用方据此回退到 service 原配置；``native_chat`` 用显式
地址与密钥直接请求（简介回退链使用）；``ModelProviderError`` 携带上游状态码，
供调用方区分“认证失败就停”和“可重试”。
"""
from . import _model_routing as routing

# 服务标识必须是 model.properties 里 service.skill-finder 的键名，改错会退化成无模型可用。
_client = routing.ServiceModelClient("skill-finder")
# 三个别名即本模块的公开面：路由调用、直连调用、上游错误类型。
try_chat = _client.try_chat_async
native_chat = routing.native_chat_async
ModelProviderError = routing.ModelProviderError
