from typing import Final

from asyncpg.exceptions import PostgresError
from pydantic import SecretStr
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError, TimeoutError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import Executable

from app.constants import DB_LIMITS

DATABASE_CONNECTION_ERRORS: Final = (
    PostgresError,
    InterfaceError,
    OperationalError,
    TimeoutError,
    OSError,
)


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: SecretStr) -> None:
        self.engine = create_async_engine(
            url.get_secret_value(),
            pool_size=DB_LIMITS.pool_size,
            max_overflow=DB_LIMITS.max_overflow,
            pool_timeout=DB_LIMITS.timeout_seconds,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "timeout": DB_LIMITS.timeout_seconds,
                "command_timeout": DB_LIMITS.timeout_seconds,
            },
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ready(self, statement: Executable) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(statement)
        except PostgresError, SQLAlchemyError, OSError:
            return False
        return True

    async def close(self) -> None:
        await self.engine.dispose()
