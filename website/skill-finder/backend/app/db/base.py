"""ORM 声明式基类。

单独抽出一个模块，是为了让模型模块只依赖基类而不依赖会话/引擎，
避免测试导入模型时顺带创建数据库连接。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类（SQLAlchemy 2 的 ``DeclarativeBase``）。

    表名、列类型与索引都在子类里显式声明，不使用自动命名约定，
    因为 ``xixi`` 库的表结构由 ``backend/sql/schema.sql`` 拥有。
    """

    pass  # noqa: PIE790
