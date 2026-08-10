import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Импортируется исключительно ради побочного эффекта — регистрации всех
# ORM-моделей (User/Conversation/Message, задача S2-02) в Base.metadata
# до того, как autogenerate начнёт сравнивать схему (см. docstring
# infrastructure/persistence/models.py). Сам объект `models` не
# используется напрямую.
from dekoder.infrastructure.persistence import models  # noqa: F401
from dekoder.infrastructure.persistence.base import Base
from dekoder.shared.config import DatabaseSettings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Единый MetaData проекта (S2-01) — единая DeclarativeBase для всех
# будущих ORM-моделей (User/Conversation/Message появятся в следующих
# задачах Sprint 2, не в этой), нужна autogenerate для их обнаружения.
target_metadata = Base.metadata

# DATABASE_URL читается через тот же централизованный механизм
# конфигурации, что и в приложении (`shared/config.py`, pydantic-
# settings), а не второй независимый способ читать `.env`, и без
# захардкоженного абсолютного пути. Используется только `DatabaseSettings`
# (не весь агрегирующий `Settings`) — миграции не должны требовать
# TELEGRAM_BOT_TOKEN/LLM_PROVIDER_API_KEY, они не имеют отношения к схеме
# базы данных. `sqlalchemy.url` из `alembic.ini` осознанно перезаписывается
# здесь — единственный источник истины для строки подключения — Settings.
config.set_main_option("sqlalchemy.url", DatabaseSettings().url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
