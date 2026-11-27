"""抓取工作台的业务服务层。

- `code_generator`：把录制历史编译成 Scrapling 脚本。
- `code_runner`：执行配方代码（进程内对着现有页面，或另起子进程）。
- `scheduler`：APScheduler 定时执行配方并回传 webhook。
- `deepseek_healer`：调用统一文本模型修复失效选择器。
- `model_hub`：统一模型入口的异步适配层。

本包不注册 HTTP 路由，也不持有全局状态（调度器单例在 `scheduler` 模块内），
所有对外行为都由 `main.py` 的路由触发。`_model_properties` 与 `_model_routing`
是 ``scripts/sync-model-routing.py`` 生成的部署副本，只读、不要在此修改。
"""
