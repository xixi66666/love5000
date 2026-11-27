"""``xixi`` 库中 skill-finder 的五张业务表模型。

表归属：``repositories`` 存仓库主数据与中文简介，``star_snapshots`` 存每日 Star 快照，
``trending_entries`` 存三个周期当前的 Top N 榜单，``collection_runs`` 存采集任务运行记录，
``last30days_reports`` 存近 30 天研究的落库结果。

约定：库与 ``website`` 共用，因此只在本服务首次接入时补建缺失表，绝不删表或重建；
表结构以 ``backend/sql/schema.sql`` 为准，模型字段必须与之保持一致。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    types,
)
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JsonText(types.TypeDecorator):
    """把 Python 的 list/dict 以 JSON 文本存进 ``TEXT`` 列。

    不使用 MySQL 原生 ``JSON`` 类型，是为了兼容 5.5 一类的旧版本实例；
    读出时自动 ``json.loads``，写入时自动 ``json.dumps``，业务代码只接触 Python 对象。
    ``None`` 原样透传，避免把空值写成字符串 ``"null"``。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        return json.loads(value)


class Repository(Base):
    """仓库主数据，同时承载中文简介。

    ``github_id`` 与 ``full_name`` 都是唯一键：前者识别同一仓库的重复采集，后者保证同名
    仓库只有一行（仓库被重建、``github_id`` 变化时会在原行上更新而不是新增）。
    ``available`` 为软删除标记（详情接口与列表都只查
    ``available=true``），``introduction`` 存简介 JSON 文本，未生成为 ``NULL``——
    详情页据此显示“暂未生成中文介绍”，而不是现查模型。
    """

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(191), unique=True)
    html_url: Mapped[str] = mapped_column(String(512))
    homepage: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 中文简介的 JSON 文本（introduction/highlights/requirements/usage/audience/domains）。
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    topics: Mapped[list[Any]] = mapped_column(JsonText)
    categories: Mapped[list[Any]] = mapped_column(JsonText)
    # 分类依据（如 topic:ai-agent），用于解释仓库为什么被归入某个分类。
    matched_rules: Mapped[list[Any]] = mapped_column(JsonText)
    stars_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # 软删除标记：仓库被删除/转私有后置 false，历史快照仍保留以便审计。
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    github_created_at: Mapped[datetime] = mapped_column(DateTime)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default="CURRENT_TIMESTAMP"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default="CURRENT_TIMESTAMP",
        onupdate=datetime.utcnow,
    )


class StarSnapshot(Base):
    """每日 Star 快照，用于详情页曲线与增量回退计算。

    唯一键是 ``(repository_id, snapshot_date)``，写入走 ``ON DUPLICATE KEY UPDATE``，
    因此同一天重复采集只更新当天数值，不会产生重复行。日期按业务时区取，
    与 ``trending_entries`` 的口径保持一致。
    """

    __tablename__ = "star_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "snapshot_date", name="uk_star_snapshots_repository_date"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id", ondelete="CASCADE")
    )
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default="CURRENT_TIMESTAMP"
    )


class TrendingEntry(Base):
    """三个周期各自的当前 Top N 榜单。

    每次采集按 ``period`` 整段替换（先删后插），所以这张表只反映“当前榜单”，
    不保留历史；需要历史曲线时查 ``star_snapshots``。
    ``(period, repository_id)`` 唯一，``stars_gained`` 是榜单页显示的周期增量。
    """

    __tablename__ = "trending_entries"
    __table_args__ = (
        UniqueConstraint(
            "period", "repository_id", name="uk_trending_entries_period_repo"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id", ondelete="CASCADE")
    )
    period: Mapped[str] = mapped_column(String(16), index=True)
    rank_position: Mapped[int] = mapped_column(Integer)
    stars_gained: Mapped[int] = mapped_column(Integer)
    stars_total: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default="CURRENT_TIMESTAMP"
    )


class CollectionRun(Base):
    """一次采集任务的运行记录。

    状态机：``RUNNING`` → ``SUCCESS`` / ``PARTIAL`` / ``FAILED``。前端通过
    ``/api/v1/stats`` 读最新一行判断刷新是否结束、是否失败；``FAILED`` 允许立即重试，
    其他状态受 30 分钟冷却限制。``error_summary`` 只供服务端排查与固定提示映射，
    原始异常文本不会直接回给浏览器。
    """

    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    trigger_type: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    # 采集结束时的 GitHub 剩余额度与重置时间；额度信息未知时为 NULL。
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_reset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default="CURRENT_TIMESTAMP"
    )


class Last30DaysReport(Base):
    """近 30 天研究结果，按方向（agent / skill）各存一行。

    ``direction`` 直接做主键，因此刷新是覆盖式更新；``payload`` 存完整的 JSON 结果，
    ``message`` 记录降级说明（例如某个来源超时），前端据此提示“结果可能不完整”。
    """

    __tablename__ = "last30days_reports"

    direction: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonText)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default="CURRENT_TIMESTAMP"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default="CURRENT_TIMESTAMP",
        onupdate=datetime.utcnow,
    )
