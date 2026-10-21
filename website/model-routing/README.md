# Python 模型路由公共客户端

`model_routing.py` 是唯一公共源码，只依赖标准库。各 Python 服务的薄适配器绑定固定服务标识，
使用随服务打包的 `_model_routing.py`；Docker/独立复制部署无需额外携带本目录。
改动公共源码后执行 `python scripts/sync-model-routing.py`，部署副本禁止手工编辑。
运行 `python scripts/sync-model-routing.py --check` 和公共 unittest 检查副本一致性。

默认网关 `http://127.0.0.1:8080`，`MODEL_HUB_URL` 可以指定其他本机端口。
`MODEL_ROUTING_STATE` 可以指定 website 选择状态文件，只保存模型 ID 和服务覆盖，不保存凭据。
生成直接调用 `try_chat(service, payload)`：一次 POST `/api/models/complete/{service}`，
返回统一模型结果，或在 HTTP 204 时返回 `None` 让服务使用原配置。
原配置的同步 HTTP 使用 `native_chat`，异步 HTTP 使用 `native_chat_async` 并传入已有连接池；
统一鉴权、JSON、响应大小、禁止重定向与脱敏错误，业务层负责提示词、解析和重试。
`ModelProviderError.status` 只包含可供重试判断的状态，不包含上游响应正文。

仅连接被拒绝且状态确认未选统一模型时允许离线原配置。超时、HTTP 错误、损坏响应或损坏状态均报错，
防止切换提供方及重复计费。完整协议与 Java 侧实现见 [统一入口文档](../../docs/model-routing.md)。

从仓库根运行：`python -m unittest discover -s website/model-routing -p 'test_*.py'`。
