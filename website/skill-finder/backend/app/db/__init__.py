"""SQLAlchemy 2 异步持久层基础设施。

``base`` 声明 ORM 基类，``models`` 定义与 ``xixi`` 库五张业务表对应的模型，
``session`` 创建全局引擎、会话工厂以及 FastAPI 依赖 ``get_db_session``。
模块导入只建立引擎对象，不连接数据库；真正的连接在首次使用会话时建立。
"""
