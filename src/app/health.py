from typing import Literal

from fastapi import APIRouter

from app.constants import Routes

router = APIRouter(tags=["health"])


@router.get(Routes.LIVENESS)
async def live() -> dict[str, Literal["alive"]]:
    return {"status": "alive"}
