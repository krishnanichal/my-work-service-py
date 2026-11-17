from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.constants import Routes
from app.infrastructure.database import Database
from app.modules.users.model import UserRow

router = APIRouter(tags=["health"])


@router.get(Routes.LIVENESS)
async def live() -> dict[str, Literal["alive"]]:
    return {"status": "alive"}


@router.get(Routes.READINESS)
async def ready(request: Request, response: Response) -> dict[str, str]:
    database: Database | None = request.app.state.database
    if database is None or not await database.ready(select(UserRow.id).limit(1)):
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}
