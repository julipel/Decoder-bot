"""
Интеграционные тесты `bootstrap.application.create_application` — фабрики,
которую реально использует `main.py` (см. ревью Спринта 1: единственный
существовавший тест `/health`, `test_health_endpoint.py`, проверяет
`composition.bootstrap.create_app()` — отдельную, не используемую в
продакшене фабрику из параллельного дерева `docs/versions/*_v2.0.md`,
claude.md §36). Совпадение поведения `/health` между двумя фабриками
случайно (обе переиспользуют `composition.health.router`) и не защищает
от регрессии в реальном `create_application` — лишний слой (lifespan,
сборка `ApplicationContainer`) там был не покрыт.

С задачи S2-01 `settings` также переопределяет `DATABASE_URL` на файл
внутри `tmp_path`: реальный lifespan теперь инициализирует постоянное
хранилище данных (`bootstrap/database.py`), и без переопределения тесты
писали бы `./data/app.db` в рабочую директорию репозитория.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.bootstrap.application import create_application
from dekoder.bootstrap.container import ApplicationContainer
from dekoder.shared.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}")
    return Settings()


def test_create_application_returns_configured_fastapi_instance(settings: Settings) -> None:
    app = create_application(settings)

    assert app.title == "dekoder"
    assert app.version == "0.1.0"


def test_health_endpoint_matches_contract_through_real_lifespan(settings: Settings) -> None:
    app = create_application(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dekoder",
        "version": "0.1.0",
    }


def test_lifespan_wires_container_with_process_user_message(settings: Settings) -> None:
    app = create_application(settings)

    with TestClient(app):
        container = app.state.container

    assert isinstance(container, ApplicationContainer)
    assert container.process_user_message is not None


def test_lifespan_initializes_database_engine_and_session_factory(settings: Settings) -> None:
    app = create_application(settings)

    with TestClient(app):
        db_engine = app.state.db_engine
        db_session_factory = app.state.db_session_factory

    assert isinstance(db_engine, AsyncEngine)
    assert isinstance(db_session_factory, async_sessionmaker)
