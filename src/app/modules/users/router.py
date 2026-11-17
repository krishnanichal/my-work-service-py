from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.constants import PAGINATION, Routes
from app.core.errors import AppError
from app.infrastructure.database import DATABASE_CONNECTION_ERRORS, Database
from app.modules.users.repository import PostgresUserRepository
from app.modules.users.schemas import UserCreate, UserPage, UserRead, UserUpdate
from app.modules.users.service import UsersService

router = APIRouter(prefix=Routes.USERS, tags=["users"])


def database_unavailable() -> AppError:
    return AppError(HTTPStatus.SERVICE_UNAVAILABLE, "service_unavailable")


async def get_users_service(request: Request) -> AsyncIterator[UsersService]:
    database: Database | None = request.app.state.database
    if database is None:
        raise database_unavailable()
    try:
        async with database.sessions() as session:
            yield UsersService(PostgresUserRepository(session))
    except DATABASE_CONNECTION_ERRORS as error:
        raise database_unavailable() from error


type Service = Annotated[UsersService, Depends(get_users_service)]


@router.get("")
async def list_users(
    service: Service,
    limit: Annotated[int, Query(ge=1, le=PAGINATION.max_limit)] = PAGINATION.default_limit,
    offset: Annotated[int, Query(ge=0, le=PAGINATION.max_offset)] = 0,
) -> UserPage:
    users, total = await service.list(offset, limit)
    return UserPage(
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=HTTPStatus.CREATED)
async def create_user(payload: UserCreate, service: Service) -> UserRead:
    return UserRead.model_validate(await service.create(payload.handle, payload.display_name))


@router.get(Routes.USER_DETAIL)
async def get_user(user_id: UUID, service: Service) -> UserRead:
    return UserRead.model_validate(await service.get(user_id))


@router.patch(Routes.USER_DETAIL)
async def update_user(user_id: UUID, payload: UserUpdate, service: Service) -> UserRead:
    return UserRead.model_validate(await service.update(user_id, payload.display_name))


@router.delete(Routes.USER_DETAIL, status_code=HTTPStatus.NO_CONTENT)
async def delete_user(user_id: UUID, service: Service) -> Response:
    await service.delete(user_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
