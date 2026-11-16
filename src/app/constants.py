from dataclasses import dataclass
from enum import StrEnum
from typing import Final


@dataclass(frozen=True, slots=True)
class AppMeta:
    name: str = "my-work-service-py"
    version: str = "0.1.0"


class Routes(StrEnum):
    LIVENESS = "/health/live"


APP_META: Final = AppMeta()
REQUEST_ID_HEADER: Final = "X-Request-ID"
PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
DEFAULT_MAX_REQUEST_BODY_BYTES: Final = 1_048_576
