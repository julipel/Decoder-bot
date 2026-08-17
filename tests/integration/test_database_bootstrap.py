"""
Тесты `bootstrap/database.py` (S2-01) — единственной точки инициализации
постоянного хранилища для реально запускаемого приложения: каталог для
SQLite-файла создаётся автоматически (только каталог, не таблицы), engine
и фабрика сессий создаются и работоспособны, ошибка инициализации
превращается в понятную `InfrastructureError`, а не игнорируется молча.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.shared.config import Settings
from dekoder.shared.errors import InfrastructureError


def _settings(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", database_url)
    return Settings()


class TestInitDatabase:
    async def test_creates_only_the_parent_directory_not_tables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "nested" / "app.db"
        settings = _settings(monkeypatch, f"sqlite+aiosqlite:///{db_path}")
        assert not db_path.parent.exists()

        engine, session_factory = await init_database(settings)
        try:
            assert db_path.parent.exists()
            # Файл базы создаётся драйвером при подключении (verify_database_connection
            # его выполняет) — но никаких таблиц внутри быть не должно (create_all не вызывается).
            assert isinstance(engine, AsyncEngine)
            assert isinstance(session_factory, async_sessionmaker)

            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                assert result.all() == []
        finally:
            await dispose_database(engine)

    async def test_session_factory_can_open_and_close_a_working_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "app.db"
        settings = _settings(monkeypatch, f"sqlite+aiosqlite:///{db_path}")

        engine, session_factory = await init_database(settings)
        try:
            async with session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                assert result.scalar_one() == 1
        finally:
            await dispose_database(engine)

    async def test_raises_infrastructure_error_when_directory_cannot_be_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Создаём файл там, где ожидается каталог — mkdir() не сможет его создать.
        blocking_file = tmp_path / "blocked"
        blocking_file.write_text("not a directory")
        settings = _settings(monkeypatch, f"sqlite+aiosqlite:///{blocking_file / 'app.db'}")

        with pytest.raises(InfrastructureError) as exc_info:
            await init_database(settings)

        assert exc_info.value.code == "DATABASE_DIRECTORY_UNAVAILABLE"

    async def test_raises_infrastructure_error_for_invalid_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(monkeypatch, "not-a-valid-database-url")

        with pytest.raises(InfrastructureError):
            await init_database(settings)
