"""``scrapling-ui`` 后端测试包。

`unittest discover -s tests` 的入口。测试分两类：`test_health` 用 FastAPI 的
``TestClient`` 直接请求应用验证路由与静态托管，`test_model_integration` 用
``AsyncMock`` 替换模型调用验证选择器修复的分支。两者都不启动 Playwright、
不监听真实端口、不发真实网络请求。
"""
