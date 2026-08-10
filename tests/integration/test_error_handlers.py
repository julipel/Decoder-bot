"""
Тесты глобального обработчика ошибок admin REST (Sprint 8, задача S8-03,
ADR-8.12) — через реальный `create_application(settings)` (полный
lifespan) с тестовыми роутами, поднимающими каждый тип ошибки. Тот же
подход, что `test_application_bootstrap.py` — не мок FastAPI-приложения.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dekoder.bootstrap.application import create_application
from dekoder.shared.config import Settings
from dekoder.shared.errors import ApplicationError, InfrastructureError, NotFoundError, ValidationError


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}")
    return Settings()


def _client_with_error_routes(settings: Settings) -> TestClient:
    app = create_application(settings)

    @app.get("/__test/validation-error")
    def _raise_validation_error() -> None:
        raise ValidationError(message="internal detail", user_message="Некорректные данные.", code="TEST_VALIDATION")

    @app.get("/__test/not-found-error")
    def _raise_not_found_error() -> None:
        raise NotFoundError(message="internal detail", user_message="Ресурс не найден.")

    @app.get("/__test/application-error")
    def _raise_application_error() -> None:
        raise ApplicationError(message="internal detail", user_message="Бизнес-ошибка.", code="TEST_APPLICATION")

    @app.get("/__test/conflict-error")
    def _raise_conflict_error() -> None:
        raise ApplicationError(
            message="internal detail", user_message="Конфликт.", code="PROFILE_ARCHIVE_DEFAULT_FORBIDDEN"
        )

    @app.get("/__test/infrastructure-error")
    def _raise_infrastructure_error() -> None:
        raise InfrastructureError(message="internal detail", user_message="Инфраструктурная ошибка.")

    @app.get("/__test/unhandled-error")
    def _raise_unhandled_error() -> None:
        raise RuntimeError("boom - internal secret detail")

    return TestClient(app, raise_server_exceptions=False)


class TestDekoderErrorHandler:
    def test_validation_error_maps_to_422(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/validation-error")

        assert response.status_code == 422
        assert response.json() == {"error": {"code": "TEST_VALIDATION", "message": "Некорректные данные."}}

    def test_not_found_error_maps_to_404(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/not-found-error")

        assert response.status_code == 404
        assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Ресурс не найден."}}

    def test_application_error_maps_to_400(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/application-error")

        assert response.status_code == 400
        assert response.json() == {"error": {"code": "TEST_APPLICATION", "message": "Бизнес-ошибка."}}

    def test_profile_archive_default_forbidden_maps_to_409_by_code_override(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/conflict-error")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN"

    def test_infrastructure_error_maps_to_502(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/infrastructure-error")

        assert response.status_code == 502
        assert response.json() == {"error": {"code": "INFRASTRUCTURE_ERROR", "message": "Инфраструктурная ошибка."}}


class TestUnhandledExceptionHandler:
    def test_unhandled_exception_maps_to_500_without_internal_details(self, settings: Settings) -> None:
        client = _client_with_error_routes(settings)
        with client:
            response = client.get("/__test/unhandled-error")

        assert response.status_code == 500
        assert response.json() == {"error": {"code": "INTERNAL_ERROR", "message": "Внутренняя ошибка сервера."}}
        assert "boom" not in response.text
        assert "secret" not in response.text

    def test_unhandled_exception_traceback_reaches_logs(
        self, settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # structlog пишет JSON в stdout через print() (shared/logging.py) —
        # capsys, не caplog (stdlib logging handler здесь не участвует).
        client = _client_with_error_routes(settings)
        with client:
            client.get("/__test/unhandled-error")

        # `_logger.exception(...)` (structlog) записывает `exc_info: true`
        # в структурированную запись — тот же приём, что и везде в проекте
        # (например, `presentation/telegram/handlers/profile.py::
        # _logger.exception("select_profile_unexpected_error")`); реальный
        # рендеринг traceback-текста — забота production-логгера/обработчика
        # exc_info на уровне stdlib logging integration, не предмет этой
        # задачи (shared/logging.py не входит в объём S8-03).
        log_output = capsys.readouterr().out
        assert "admin_request_unhandled_error" in log_output
        assert '"exc_info": true' in log_output
