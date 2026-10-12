from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Text, cast, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.classifier import Classification
from app.collector.github_client import GitHubRepository
from app.db.models import Repository


class RepositoryStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, repo: GitHubRepository, classification: Classification) -> Repository:
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
        result = await self._session.execute(
            select(Repository).where(Repository.available.is_(True))
        )
        return list(result.scalars().all())

    async def list_by_ids(self, ids: list[int]) -> list[Repository]:
        if not ids:
            return []
        result = await self._session.execute(
            select(Repository).where(Repository.id.in_(ids))
        )
        return list(result.scalars().all())

    async def list_without_introduction(
        self, *, category: str | None = None, limit: int = 5
    ) -> list[Repository]:
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
        await self._session.execute(
            Repository.__table__.update()
            .where(Repository.github_id == github_id)
            .values(introduction=text)
        )

    async def mark_unavailable(self, github_ids: list[int]) -> None:
        if not github_ids:
            return
        await self._session.execute(
            Repository.__table__.update()
            .where(Repository.github_id.in_(github_ids))
            .values(available=False)
        )
