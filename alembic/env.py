import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.constants import DB_LIMITS
from app.core.config import DatabaseSettings
from app.modules.users.model import UserRow

metadata = UserRow.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate_online(url: str) -> None:
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={"timeout": DB_LIMITS.timeout_seconds},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


def main() -> None:
    database_url = DatabaseSettings().database_url
    if database_url is None:
        raise RuntimeError("Set APP_DATABASE_URL before running Alembic")
    url = database_url.get_secret_value()
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        asyncio.run(migrate_online(url))


main()
