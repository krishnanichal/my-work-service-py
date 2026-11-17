import json
import os
from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.constants import (
    APP_SECRETS_ENV,
    DATABASE_IDENTITY_QUERY_ARGS,
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    WORK_API_DATABASE_URL_KEY,
)


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

    @model_validator(mode="before")
    @classmethod
    def read_runtime_bundle(cls, data: object) -> object:
        raw_bundle = os.environ.get(APP_SECRETS_ENV)
        if raw_bundle is None or not isinstance(data, dict):
            return data

        try:
            bundle = json.loads(raw_bundle)
        except json.JSONDecodeError, RecursionError:
            raise ValueError(f"{APP_SECRETS_ENV} must be a JSON object") from None
        if not isinstance(bundle, dict):
            raise ValueError(f"{APP_SECRETS_ENV} must be a JSON object")

        database_url = bundle.get(WORK_API_DATABASE_URL_KEY)
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError(f"{APP_SECRETS_ENV} requires a nonempty {WORK_API_DATABASE_URL_KEY}")

        return {**data, "database_url": SecretStr(database_url)}

    @model_validator(mode="after")
    def validate_bundled_database_role(self) -> Self:
        if APP_SECRETS_ENV in os.environ and self.database_url is not None:
            url = make_url(self.database_url.get_secret_value())
            if (
                url.username != f"work_api_{self.env}_runtime"
                or url.database != f"app_db_work_{self.env}"
                or not url.host
                or not url.password
                or not DATABASE_IDENTITY_QUERY_ARGS.isdisjoint(url.query)
            ):
                raise ValueError(
                    f"{WORK_API_DATABASE_URL_KEY} must use the Work API runtime login and "
                    "database for APP_ENV"
                )
        return self

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
