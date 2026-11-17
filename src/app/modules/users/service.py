from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.modules.users.domain import User
from app.modules.users.repository import UserHandleConflict, UserRepository


def user_not_found() -> AppError:
    return AppError(HTTPStatus.NOT_FOUND, "user_not_found", "The requested user does not exist.")


class UsersService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def list(self, offset: int, limit: int) -> tuple[list[User], int]:
        return await self.repository.list(offset, limit)

    async def get(self, user_id: UUID) -> User:
        user = await self.repository.get(user_id)
        if user is None:
            raise user_not_found()
        return user

    async def create(self, handle: str, display_name: str) -> User:
        user = User(uuid4(), handle.casefold(), display_name, datetime.now(UTC))
        try:
            return await self.repository.create(user)
        except UserHandleConflict as error:
            raise AppError(
                HTTPStatus.CONFLICT, "user_handle_conflict", "Choose a different handle."
            ) from error

    async def update(self, user_id: UUID, display_name: str) -> User:
        user = await self.repository.update_display_name(user_id, display_name)
        if user is None:
            raise user_not_found()
        return user

    async def delete(self, user_id: UUID) -> None:
        if not await self.repository.delete(user_id):
            raise user_not_found()
