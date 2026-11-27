"""异步工作台适配公共模型客户端。

把统一模型入口的异步客户端收敛成两个可直接调用的函数，供 `deepseek_healer` 使用：

- ``try_chat``：先问统一模型网关。返回 ``None`` 只代表「应该改用服务原配置」——
  网关回 204，或连接被拒且确认本服务没有统一选择；超时与其它 HTTP 错误一律抛出，
  不会自动换模型。同步请求被 ``asyncio.to_thread`` 包成协程，不阻塞事件循环。
- ``native_chat``：按服务原配置直连 ``/chat/completions``，需要调用方自己建
  ``httpx.AsyncClient`` 并传超时；非 2xx 抛 ``ModelProviderError``。

``_model_routing`` 是 ``scripts/sync-model-routing.py`` 生成的部署副本，不是源码，
修改它会在下次同步时被覆盖；需要改逻辑请改 ``website/model-routing`` 下的公共源码。
"""
from . import _model_routing as routing

_client = routing.ServiceModelClient("scrapling-ui")
try_chat = _client.try_chat_async
native_chat = routing.native_chat_async
