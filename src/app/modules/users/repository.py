from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.users.domain import User
from app.modules.users.model import UserRow


class UserHandleConflict(Exception):
    pass


class UserRepository(Protocol):
    async def list(self, offset: int, limit: int) -> tuple[list[User], int]: ...

    async def get(self, user_id: UUID) -> User | None: ...

    async def create(self, user: User) -> User: ...

    async def update_display_name(self, user_id: UUID, display_name: str) -> User | None: ...

    async def delete(self, user_id: UUID) -> bool: ...


class PostgresUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, offset: int, limit: int) -> tuple[list[User], int]:
        page = (
            select(UserRow)
            .order_by(UserRow.created_at, UserRow.id)
            .offset(offset)
            .limit(limit)
            .subquery()
        )
        count = select(func.count().label("total")).select_from(UserRow).subquery()
        page_user = aliased(UserRow, page)
        statement = (
            select(page_user, count.c.total)
            .select_from(count.outerjoin(page, true()))
            .order_by(page_user.created_at, page_user.id)
        )
        rows = (await self.session.execute(statement)).tuples().all()
        return [row.to_user() for row, _ in rows if row is not None], int(rows[0][1])

    async def get(self, user_id: UUID) -> User | None:
        row = await self.session.get(UserRow, user_id)
        return row.to_user() if row is not None else None

    async def create(self, user: User) -> User:
        statement = (
            insert(UserRow)
            .values(
                id=user.id,
                handle=user.handle,
                display_name=user.display_name,
                created_at=user.created_at,
            )
            .on_conflict_do_nothing(index_elements=[UserRow.handle])
            .returning(UserRow)
        )
        async with self.session.begin():
            row = await self.session.scalar(statement)
        if row is None:
            raise UserHandleConflict
        return row.to_user()

    async def update_display_name(self, user_id: UUID, display_name: str) -> User | None:
        statement = (
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(display_name=display_name)
            .returning(UserRow)
        )
        async with self.session.begin():
            row = await self.session.scalar(statement)
        return row.to_user() if row is not None else None

    async def delete(self, user_id: UUID) -> bool:
        statement = delete(UserRow).where(UserRow.id == user_id).returning(UserRow.id)
        async with self.session.begin():
            return await self.session.scalar(statement) is not None
