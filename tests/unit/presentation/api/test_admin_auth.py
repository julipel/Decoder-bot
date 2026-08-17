"""
Тесты `require_admin_api_key` (Sprint 8, задача S8-02, ADR-8.3) — все три
исхода авторизации через минимальное FastAPI-приложение с одним тестовым
роутом, защищённым зависимостью (не мок `Request` вручную — реальный
HTTP-запрос через `TestClient` точнее проверяет заголовок/`Security`-
резолюцию, которую FastAPI выполняет сам).
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dekoder.presentation.api.dependencies.auth import require_admin_api_key
from dekoder.shared.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ADMIN_API_KEY", "correct-admin-key")
    return Settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = FastAPI()
    app.state.settings = settings

    @app.get("/protected", dependencies=[Depends(require_admin_api_key)])
    def _protected() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


class TestRequireAdminApiKey:
    def test_missing_header_returns_401(self, client: TestClient) -> None:
        response = client.get("/protected")

        assert response.status_code == 401

    def test_incorrect_key_returns_401(self, client: TestClient) -> None:
        response = client.get("/protected", headers={"X-Admin-Api-Key": "wrong-key"})

        assert response.status_code == 401

    def test_correct_key_passes(self, client: TestClient) -> None:
        response = client.get("/protected", headers={"X-Admin-Api-Key": "correct-admin-key"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_missing_and_incorrect_key_bodies_do_not_leak_expected_key(self, client: TestClient) -> None:
        missing = client.get("/protected")
        incorrect = client.get("/protected", headers={"X-Admin-Api-Key": "wrong-key"})

        assert "correct-admin-key" not in missing.text
        assert "correct-admin-key" not in incorrect.text

    def test_auth_failure_is_logged_without_the_key(
        self, client: TestClient, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client.get("/protected", headers={"X-Admin-Api-Key": "wrong-key"})

        log_output = capsys.readouterr().out
        assert "correct-admin-key" not in log_output
        assert "wrong-key" not in log_output


class TestAdminSettings:
    def test_fails_fast_without_admin_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pydantic import ValidationError

        from dekoder.shared.config import AdminSettings

        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            AdminSettings(_env_file=None)  # type: ignore[call-arg]

    def test_default_health_check_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from dekoder.shared.config import AdminSettings

        monkeypatch.setenv("ADMIN_API_KEY", "some-key")
        settings = AdminSettings(_env_file=None)  # type: ignore[call-arg]

        assert settings.health_check_timeout == 3.0

    def test_api_key_not_shown_in_repr_or_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from dekoder.shared.config import AdminSettings

        monkeypatch.setenv("ADMIN_API_KEY", "super-secret-admin-key")
        settings = AdminSettings(_env_file=None)  # type: ignore[call-arg]

        assert "super-secret-admin-key" not in str(settings)
        assert "super-secret-admin-key" not in repr(settings)
        assert settings.api_key.get_secret_value() == "super-secret-admin-key"
