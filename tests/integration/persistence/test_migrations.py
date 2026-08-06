"""
Тест первой Alembic-миграции (задача S2-02, `alembic/versions/
a96ab72bfa8a_create_users_conversations_messages.py`), схемной миграции
Sprint 3 (задача S3-03, `alembic/versions/
14bf7e3ae815_create_profiles_user_active_profiles.py`) и сид-миграции
каталога профилей (задача S3-04, `alembic/versions/
27c4e9f2a103_seed_profile_catalog.py`): `upgrade head` создаёт все
таблицы/индексы/ограничения и вносит сид-данные, `downgrade base`
удаляет всё полностью, повторный `upgrade head` снова проходит без
ошибок — на временной SQLite-базе (`tmp_path`, НЕ рабочая БД из
`./data/app.db`).

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


def _profile_rows(db_path: Path) -> list[tuple[str, str, int, int, int]]:
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.execute("SELECT id, name, is_default, status = 'active', is_system FROM profiles")
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

        assert {
            "users",
            "conversations",
            "messages",
            "profiles",
            "user_active_profiles",
            "memory_records",
            "knowledge_documents",
        } <= table_names
        assert {
            "ix_conversations_user_id",
            "uq_conversations_active_user",
            "ix_messages_conversation_created",
            "uq_profiles_is_default",
            "ix_memory_records_user_status",
            "ix_knowledge_documents_checksum",
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

        profiles_sql = next(sql for type_, name, sql in objects if type_ == "table" and name == "profiles")
        assert "ck_profiles_status" in profiles_sql

        user_active_profiles_sql = next(
            sql for type_, name, sql in objects if type_ == "table" and name == "user_active_profiles"
        )
        assert "fk_user_active_profiles_user_id_users" in user_active_profiles_sql
        assert "fk_user_active_profiles_profile_id_profiles" in user_active_profiles_sql

        profiles_partial_index_sql = next(
            sql for type_, name, sql in objects if type_ == "index" and name == "uq_profiles_is_default"
        )
        assert "WHERE is_default = 1" in profiles_partial_index_sql

        memory_records_sql = next(sql for type_, name, sql in objects if type_ == "table" and name == "memory_records")
        assert "ck_memory_records_category" in memory_records_sql
        assert "ck_memory_records_source" in memory_records_sql
        assert "ck_memory_records_status" in memory_records_sql
        assert "ck_memory_records_confidence" in memory_records_sql
        assert "fk_memory_records_user_id_users" in memory_records_sql

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
        assert {
            "users",
            "conversations",
            "messages",
            "profiles",
            "user_active_profiles",
            "memory_records",
            "knowledge_documents",
        } <= table_names

    def test_downgrade_to_pre_profile_schema_removes_only_profile_tables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Откат до ревизии S2-02 (seed S3-04 + schema S3-03) не трогает Sprint 2 (users/conversations/messages)."""
        db_path = tmp_path / "migration-partial-downgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        table_names_before = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert {"profiles", "user_active_profiles"} <= table_names_before

        # Ревизия a96ab72bfa8a (S2-02) — сразу перед схемной миграцией профилей.
        command.downgrade(config, "a96ab72bfa8a")

        table_names_after = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "profiles" not in table_names_after
        assert "user_active_profiles" not in table_names_after
        assert {"users", "conversations", "messages"} <= table_names_after


class TestProfileCatalogSeedMigration:
    """Тесты сид-миграции каталога профилей (задача S3-04, ADR-3.4)."""

    def test_upgrade_head_creates_exactly_four_active_system_profiles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "seed-upgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")

        rows = _profile_rows(db_path)
        assert len(rows) == 4
        assert all(is_active for _, _, _, is_active, _ in rows)
        assert all(is_system for _, _, _, _, is_system in rows)

    def test_upgrade_head_creates_exactly_one_default_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "seed-default.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")

        rows = _profile_rows(db_path)
        default_rows = [row for row in rows if row[2] == 1]
        assert len(default_rows) == 1
        assert default_rows[0][1] == "Деловой"

    def test_downgrade_to_pre_seed_removes_only_seed_rows_not_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "seed-downgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        assert len(_profile_rows(db_path)) == 4

        # Явный целевой ревижн "14bf7e3ae815" (схема profiles/user_active_
        # profiles, до сид-миграции 27c4e9f2a103), а не относительный "-1":
        # с задачи S5-04 head — уже 161899ea36c0 (memory_records), поэтому
        # "-1" откатывал бы только эту миграцию, не сид-данные профилей.
        command.downgrade(config, "14bf7e3ae815")

        # Схема (таблица profiles) остаётся — откатились только вставленные строки.
        table_names = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "profiles" in table_names
        assert _profile_rows(db_path) == []

    def test_upgrade_head_after_seed_downgrade_restores_same_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "seed-cycle.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        ids_before = {row[0] for row in _profile_rows(db_path)}

        # См. комментарий выше — явный ревижн, не относительный "-1".
        command.downgrade(config, "14bf7e3ae815")
        command.upgrade(config, "head")
        ids_after = {row[0] for row in _profile_rows(db_path)}

        assert ids_before == ids_after
        assert len(ids_after) == 4


class TestMemoryRecordsSchemaMigration:
    """Тесты схемной миграции memory_records (Sprint 5, задача S5-04, ADR-5.7) — без сид-данных."""

    def test_upgrade_head_creates_memory_records_without_seed_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "memory-upgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")

        table_names = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "memory_records" in table_names

        connection = sqlite3.connect(db_path)
        try:
            row_count = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()[0]
        finally:
            connection.close()
        # ADR-5.7: только схемная миграция, никакого сид-инсерта, в отличие от profiles.
        assert row_count == 0

    def test_downgrade_to_pre_memory_schema_removes_only_memory_records_table(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "memory-downgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        table_names_before = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "memory_records" in table_names_before

        # Явный целевой ревижн "27c4e9f2a103" (до миграции memory_records
        # 161899ea36c0), а не относительный "-1": с задачи S6-04 head — уже
        # 82d9884e32a2 (knowledge_documents), поэтому "-1" откатывал бы
        # только её, не memory_records (тот же урок, что и в комментарии
        # `test_downgrade_to_pre_seed_removes_only_seed_rows_not_schema`
        # выше про сдвиг head в Sprint 5).
        command.downgrade(config, "27c4e9f2a103")

        table_names_after = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "memory_records" not in table_names_after
        # Профили (S3-03/S3-04) не задеты — эта миграция откатывается независимо от них.
        assert {"profiles", "user_active_profiles"} <= table_names_after
        assert len(_profile_rows(db_path)) == 4

    def test_upgrade_head_after_downgrade_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "memory-cycle.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        command.downgrade(config, "27c4e9f2a103")
        command.upgrade(config, "head")

        table_names = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "memory_records" in table_names


class TestKnowledgeDocumentsSchemaMigration:
    """Тесты схемной миграции knowledge_documents (Sprint 6, задача S6-04, ADR-6.1/6.2) — без сид-данных."""

    def test_upgrade_head_creates_knowledge_documents_without_seed_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "knowledge-upgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")

        objects = _schema_objects(db_path)
        table_names = {name for type_, name, _ in objects if type_ == "table"}
        assert "knowledge_documents" in table_names

        knowledge_sql = next(sql for type_, name, sql in objects if type_ == "table" and name == "knowledge_documents")
        assert "ck_knowledge_documents_document_type" in knowledge_sql
        assert "ck_knowledge_documents_status" in knowledge_sql

        index_names = {name for type_, name, _ in objects if type_ == "index"}
        assert "ix_knowledge_documents_checksum" in index_names
        checksum_index_sql = next(
            sql for type_, name, sql in objects if type_ == "index" and name == "ix_knowledge_documents_checksum"
        )
        assert "UNIQUE" in checksum_index_sql

        connection = sqlite3.connect(db_path)
        try:
            row_count = connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
        finally:
            connection.close()
        assert row_count == 0

    def test_downgrade_minus_one_removes_only_knowledge_documents_table(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "knowledge-downgrade.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        table_names_before = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "knowledge_documents" in table_names_before

        # knowledge_documents — текущий head (82d9884e32a2): "-1" здесь
        # безопасен ровно до следующей миграции поверх него.
        command.downgrade(config, "-1")

        table_names_after = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "knowledge_documents" not in table_names_after
        assert {"memory_records", "profiles", "user_active_profiles"} <= table_names_after

    def test_upgrade_head_after_downgrade_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "knowledge-cycle.db"
        config = _alembic_config(f"sqlite+aiosqlite:///{db_path}", monkeypatch)

        command.upgrade(config, "head")
        command.downgrade(config, "-1")
        command.upgrade(config, "head")

        table_names = {name for type_, name, _ in _schema_objects(db_path) if type_ == "table"}
        assert "knowledge_documents" in table_names
