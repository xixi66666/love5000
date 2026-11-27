"""数据库引擎、会话工厂与 FastAPI 会话依赖。

``engine`` 使用连接池并为每条连接开启 ``pool_pre_ping``，避免腾讯云 MySQL 主动断开
空闲连接后第一次请求报错；``expire_on_commit=False`` 让提交后仍能读取 ORM 对象的
字段（返回响应时不再触发隐式查询）。

会话所有权：``get_db_session`` 只负责打开与关闭，**不提交也不回滚**——
提交由具体业务（采集服务、last30days 服务）在事务边界处显式执行，
这样路由层能自由组合多个只读查询而不产生隐式写事务。
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# 全局引擎：连接串已在 settings 中脱敏派生，这里不打印任何连接参数。
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：为每个请求提供一个会话，请求结束后关闭。

    使用 ``async with`` 打开会话，退出时由 SQLAlchemy 归还连接；本函数不做
    ``commit``——只读路由不需要事务，写入语义由服务层显式提交（例如
    ``refresh_ranking``）。因此路由里抛出的异常不会悄悄写入半成品数据。

    Yields:
        绑定了当前请求的 :class:`AsyncSession`。
    """
    async with async_session_factory() as session:
        yield session
