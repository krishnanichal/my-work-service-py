from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserLimits:
    handle_min_length: int = 3
    handle_max_length: int = 32
    handle_pattern: str = r"^[A-Za-z0-9_.-]+$"
    display_name_max_length: int = 100
    display_name_pattern: str = r"^[^\x00]+$"


USER_LIMITS: Final = UserLimits()


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    handle: str
    display_name: str
    created_at: datetime
