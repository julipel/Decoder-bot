"""
Тест первой Alembic-миграции (задача S2-02, `alembic/versions/
a96ab72bfa8a_create_users_conversations_messages.py`): `upgrade head`
создаёт все таблицы/индексы/ограничения, `downgrade base` удаляет их
полностью, повторный `upgrade head` снова проходит без ошибок — на
временной SQLite-базе (`tmp_path`, НЕ рабочая БД из `./data/app.db`).

Тесты синхронные (обычные функции, не `async def`): `alembic/env.py`
запускает миграции через `asyncio.run(...)` (задача S2-01) — вызов из уже
работающего event loop (как было бы в `async def`-тесте под
`pytest-asyncio`, `asyncio_mode = "auto"`) завершился бы `RuntimeError:
asyncio.run() cannot be called from a running event loop`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    # `alembic/env.py` читает строку подключения через `DatabaseSettings().url`
    # (та же переменная окружения `DATABASE_URL`, что и в приложении, S2-01) —
    # переопределяем её, а не второй независимый способ передать URL.
    monkeypatch.setenv("DATABASE_URL", database_url)
    return Config(str(_REPO_ROOT / "alembic.ini"))


def _schema_objects(db_path: Path) -> list[tuple[str, str, str]]:
    connection = sqlite3.connect(db_path)
    try:
        # `tbl_name` (не `name`) исключает и саму таблицу `alembic_version`,
        # и её неявный автоиндекс первичного ключа (`sqlite_autoindex_
        # alembic_version_1`) — фильтр по `name` пропускал бы автоиндекс.
        cursor = connection.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name != 'alembic_version'")
        return cursor.fetchall()
    finally:
        connection.close()


class TestInitialMigrationCycle:
    def test_upgrade_creates_full_schema(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "migration-upgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")

        objects = _schema_objects(db_path)
        table_names = {name for type_, name, _ in objects if type_ == "table"}
        index_names = {name for type_, name, _ in objects if type_ == "index"}

        assert {"users", "conversations", "messages"} <= table_names
        assert {
            "ix_conversations_user_id",
            "uq_conversations_active_user",
            "ix_messages_conversation_created",
        } <= index_names

        users_sql = next(sql for type_, name, sql in objects if type_ == "table" and name == "users")
        assert "uq_users_telegram_user_id" in users_sql

        messages_sql = next(sql for type_, name, sql in objects if type_ == "table" and name == "messages")
        assert "ck_messages_role" in messages_sql
        assert "ck_messages_content_not_empty" in messages_sql

        partial_index_sql = next(
            sql for type_, name, sql in objects if type_ == "index" and name == "uq_conversations_active_user"
        )
        assert "WHERE closed_at IS NULL" in partial_index_sql

    def test_downgrade_removes_everything_and_upgrade_again_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "migration-cycle.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        assert _schema_objects(db_path) != []

        command.downgrade(config, "base")
        assert _schema_objects(db_path) == []

        # Повторный upgrade head после полного downgrade не должен падать.
        command.upgrade(config, "head")
        table_names = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert {"users", "conversations", "messages"} <= table_names
