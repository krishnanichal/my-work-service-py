from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.domain import USER_LIMITS


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    handle: str = Field(
        min_length=USER_LIMITS.handle_min_length,
        max_length=USER_LIMITS.handle_max_length,
        pattern=USER_LIMITS.handle_pattern,
    )
    display_name: str = Field(
        min_length=1,
        max_length=USER_LIMITS.display_name_max_length,
        pattern=USER_LIMITS.display_name_pattern,
    )


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    display_name: str = Field(
        min_length=1,
        max_length=USER_LIMITS.display_name_max_length,
        pattern=USER_LIMITS.display_name_pattern,
    )


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    handle: str
    display_name: str
    created_at: datetime


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int
