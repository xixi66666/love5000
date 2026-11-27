"""skill-finder 后端应用包（FastAPI + SQLAlchemy 2 异步）。

子包职责：``api`` 提供 ``/api/v1`` 路由与统一错误响应，``collector`` 负责 GitHub
Trending 采集与元数据补全，``core`` 负责配置与 APScheduler，``db`` 放 ORM 模型与会话，
``repositories`` 封装对 ``xixi`` 库五张业务表的读写，``schemas`` 定义响应模型，
``services`` 承载趋势、统计与中文简介逻辑，``last30days`` 是多源近 30 天研究。

应用在 ``app.main`` 中组装，服务端口 5177；数据库凭据、GitHub Token 与 ADMIN_KEY
只存放在 ``backend/.env`` / ``backend/.secrets/``，不在包初始化阶段读取或打印。
"""
