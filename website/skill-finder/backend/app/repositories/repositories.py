"""``repositories`` 表（仓库主数据）的访问对象。

写路径使用 MySQL 的 ``INSERT ... ON DUPLICATE KEY UPDATE``：``github_id`` 与
``full_name`` 都有唯一键，同一仓库被反复采集时只更新字段、不新增行。
读取路径包括榜单候选、按 id 批量取、缺失介绍的仓库筛选等。

事务约定：所有方法只 ``flush``/``execute``，不提交；``upsert`` 之后重新查询一次
（``populate_existing``）是为了拿到数据库侧写入的默认值，也保证同一会话里后续代码
用的对象与库中一致。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Text, cast, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.classifier import Classification
from app.collector.github_client import GitHubRepository
from app.db.models import Repository, TrendingEntry


class RepositoryStore:
    """仓库主数据仓储。

    只做语句组装：会话由调用方（采集服务或后台补全任务）提供并负责提交，
    因此可以在同一事务里连续写入仓库、快照与榜单。
    """

    def __init__(self, session: AsyncSession) -> None:
        """只保存会话引用：本仓储不打开、不提交、不关闭会话。

        Args:
            session: 调用方打开的会话，事务边界由调用方决定。
        """
        self._session = session

    async def daily_report_candidates(self, since: datetime) -> list[tuple]:
        """挑选当日日报候选（最多 10 个）。

        只统计 ``since`` 之后抓取过的 ``daily`` 榜单行，按增量降序、名次升序取前 10；
        已软删除（``available=false``）的仓库不参与。日报流水线用它决定今天讲哪几个项目。

        Args:
            since: 抓取时间下界（UTC），通常是当天 0 点。

        Returns:
            ``(Repository, TrendingEntry)`` 二元组列表；无候选时为空列表。
        """
        rows = await self._session.execute(
            select(Repository, TrendingEntry)
            .join(TrendingEntry, Repository.id == TrendingEntry.repository_id)
            .where(
                Repository.available.is_(True),
                TrendingEntry.period == "daily",
                TrendingEntry.fetched_at >= since,
            )
            .order_by(TrendingEntry.stars_gained.desc(), TrendingEntry.rank_position.asc())
            .limit(10)
        )
        return list(rows.all())

    async def upsert(self, repo: GitHubRepository, classification: Classification) -> Repository:
        """按唯一键插入或更新仓库，并返回库中的最新对象。

        冲突时用 ``stmt.inserted`` 引用本次要写入的值，因此更新只覆盖本次采集到的字段，
        不会把 ``created_at`` 重置；``available`` 强制写回 ``True``，让重新出现的仓库
        自动恢复可见。

        Args:
            repo: GitHub API 快照。
            classification: 分类结果，写入 ``categories`` 与 ``matched_rules``。

        Returns:
            重新查询（``populate_existing``）后的 ORM 对象，字段与数据库一致。

        Raises:
            sqlalchemy.exc.SQLAlchemyError: 唯一键冲突以外的写入失败原样上抛，
                由采集服务决定是否把本轮标成失败。
        """
        now = datetime.now(UTC)
        values = {
            "github_id": repo.github_id,
            "owner": repo.owner,
            "name": repo.name,
            "full_name": repo.full_name,
            "html_url": repo.html_url,
            "homepage": repo.homepage,
            "description": repo.description,
            "language": repo.language,
            "topics": repo.topics,
            "categories": list(classification.categories),
            "matched_rules": list(classification.matched_rules),
            "stars_count": repo.stars_count,
            "forks_count": repo.forks_count,
            "open_issues_count": repo.open_issues_count,
            "archived": repo.archived,
            "disabled": repo.disabled,
            "available": True,
            "github_created_at": repo.github_created_at,
            "github_updated_at": repo.github_updated_at,
            "last_synced_at": now,
        }
        stmt = insert(Repository).values(**values)
        update_columns = {
            key: stmt.inserted[key]
            for key in values
            if key not in ("created_at", "updated_at")
        }
        stmt = stmt.on_duplicate_key_update(**update_columns)
        await self._session.execute(stmt)

        result = await self._session.execute(
            select(Repository)
            .where(Repository.github_id == repo.github_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def list_available(self) -> list[Repository]:
        """返回全部可见仓库（未软删除）。

        Returns:
            ``available=true`` 的仓库列表，无排序；量级小，供后台任务遍历使用。
        """
        result = await self._session.execute(
            select(Repository).where(Repository.available.is_(True))
        )
        return list(result.scalars().all())

    async def list_by_ids(self, ids: list[int]) -> list[Repository]:
        """按主键批量取仓库。

        Args:
            ids: 主键列表；为空时直接返回空列表，不发出空 ``IN ()`` 查询。

        Returns:
            命中的仓库，顺序不保证与 ``ids`` 一致。
        """
        if not ids:
            return []
        result = await self._session.execute(
            select(Repository).where(Repository.id.in_(ids))
        )
        return list(result.scalars().all())

    async def list_without_introduction(
        self, *, category: str | None = None, limit: int = 5
    ) -> list[Repository]:
        """挑出还没有中文介绍的仓库，按总 Star 降序。

        ``categories`` 是 JSON 文本，因此分类过滤用 ``LIKE '%"AGENT"%'`` 匹配带引号的
        完整元素值，避免 ``AGENT`` 误命中 ``AGENTS`` 之类的子串。

        Args:
            category: 限定分类，``None`` 表示不限。
            limit: 返回条数上限。

        Returns:
            待补全介绍的仓库列表（``available=true`` 且 ``introduction IS NULL``）。
        """
        query = select(Repository).where(
            Repository.available.is_(True),
            Repository.introduction.is_(None),
        )
        if category:
            query = query.where(
                cast(Repository.categories, Text).like(f'%"{category}"%')
            )
        query = query.order_by(
            Repository.stars_count.desc(),
            Repository.id.asc(),
        ).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update_introduction(self, github_id: int, text: str) -> None:
        """写入一个仓库的中文简介。

        用 ``github_id`` 而不是主键定位，因为调用方通常只持有 GitHub 侧标识；
        已存在的简介会被覆盖（补全流程只对 ``introduction IS NULL`` 的仓库调用）。

        Args:
            github_id: GitHub 的仓库 ID。
            text: 简介 JSON 文本，结构见 ``_parse_introduction``。
        """
        await self._session.execute(
            Repository.__table__.update()
            .where(Repository.github_id == github_id)
            .values(introduction=text)
        )

    async def mark_unavailable(self, github_ids: list[int]) -> None:
        """批量软删除（置 ``available=false``），保留历史快照。

        Args:
            github_ids: 需要隐藏的仓库 GitHub ID；为空时直接返回，不发空更新。
        """
        if not github_ids:
            return
        await self._session.execute(
            Repository.__table__.update()
            .where(Repository.github_id.in_(github_ids))
            .values(available=False)
        )
