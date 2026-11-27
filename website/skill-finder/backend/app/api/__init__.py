"""HTTP 接口层。

``dependencies`` 提供路由依赖（服务实例、``X-Admin-Key`` 鉴权），``errors`` 定义统一
错误体与三类异常处理器，``v1`` 汇总挂在 ``/api/v1`` 下的具体路由模块。
本层只做参数校验、依赖注入与响应组装，SQL 与外部请求分别下沉到 ``repositories``
和 ``services`` / ``collector``。
"""
