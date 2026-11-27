"""把统一模型客户端绑定到 ``python-a`` 服务标识的薄适配层。

对外只暴露两个模块级可调用对象：

- ``try_chat(payload)``：先请求 website 的统一模型入口
  ``POST /api/models/complete/python-a``。命中统一选择时返回模型结果；返回 HTTP 204
  或仅在“连接被拒绝且状态确认没有统一选择”时返回 ``None``，表示调用方改用服务原配置。
- ``native_chat(url, key, payload, timeout=90, headers=None)``：直连服务原配置的
  提供方，只允许 https 或回环 http，鉴权头在此拼装，错误统一收敛为
  ``ModelProviderError``（不携带响应正文，避免泄漏凭据）。

模型与密钥只来自仓库根目录 ``model.properties``（``service.python-a`` 与
``deepseek.*`` / ``vision.*``），本项目不读取模型相关的环境变量。本模块不写磁盘，
统一模型的选择结果由 website 保存在根 ``.runtime/model-routing.json``，这里只读。

``_model_routing`` 是 ``scripts/sync-model-routing.py`` 生成的部署副本，随服务一起
打包，只改 ``website/model-routing`` 下的公共源码，不要手工改副本；本文件只负责
绑定服务标识，改服务标识必须同步 ``model.properties``。
"""
from . import _model_routing as routing

# 服务标识固定为 python-a，website 的模型入口据此解析跟随主页 / 服务原配置 / 独立模型。
_client = routing.ServiceModelClient("python-a")
# 以模块属性形式转发，调用方（server.py、研究分析）无需感知 ServiceModelClient。
try_chat = _client.try_chat
native_chat = routing.native_chat
