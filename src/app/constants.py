from dataclasses import dataclass
from enum import StrEnum
from typing import Final


@dataclass(frozen=True, slots=True)
class AppMeta:
    name: str = "my-work-service-py"
    version: str = "0.1.0"


class Routes(StrEnum):
    LIVENESS = "/health/live"
    READINESS = "/health/ready"
    USERS = "/api/v1/users"
    USER_DETAIL = "/{user_id}"


@dataclass(frozen=True, slots=True)
class DatabaseLimits:
    pool_size: int = 3
    max_overflow: int = 2
    timeout_seconds: int = 5


@dataclass(frozen=True, slots=True)
class Pagination:
    default_limit: int = 20
    max_limit: int = 100
    max_offset: int = 1_000_000


APP_META: Final = AppMeta()
DB_LIMITS: Final = DatabaseLimits()
PAGINATION: Final = Pagination()
REQUEST_ID_HEADER: Final = "X-Request-ID"
PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
PROBLEM_RESPONSE_HEADERS: Final = frozenset({"allow", "retry-after", "www-authenticate"})
UNMATCHED_ROUTE: Final = "unmatched"
DEFAULT_MAX_REQUEST_BODY_BYTES: Final = 1_048_576
