from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.constants import DEFAULT_MAX_REQUEST_BODY_BYTES


class Environment(StrEnum):
    DEV = "dev"
    PRD = "prd"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", hide_input_in_errors=True)

    database_url: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError, ValueError:
            raise ValueError("APP_DATABASE_URL must be a PostgreSQL connection URL") from None
        if url.drivername not in {"postgresql", "postgresql+asyncpg"} or not url.database:
            raise ValueError("APP_DATABASE_URL must be a PostgreSQL URL with a database name")
        return SecretStr(
            url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
        )


class Settings(DatabaseSettings):
    env: Environment = Environment.DEV
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    debug: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: list[str] = Field(default_factory=list)
    max_request_body_bytes: int = Field(default=DEFAULT_MAX_REQUEST_BODY_BYTES, gt=0)

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        if self.env is Environment.PRD:
            if self.debug:
                raise ValueError("APP_DEBUG must be false in production")
            if (
                "allowed_hosts" not in self.model_fields_set
                or not self.allowed_hosts
                or any("*" in host for host in self.allowed_hosts)
            ):
                raise ValueError("Production requires explicit APP_ALLOWED_HOSTS")
            if "*" in self.cors_origins:
                raise ValueError("Production requires explicit APP_CORS_ORIGINS")
            if self.database_url is None:
                raise ValueError("Production requires APP_DATABASE_URL")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
