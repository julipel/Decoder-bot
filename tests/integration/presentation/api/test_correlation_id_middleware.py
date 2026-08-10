"""
Интеграционные тесты `CorrelationIdMiddleware` (Sprint 9, задача S9-03,
ADR-9.3) — через реальный `create_application(settings)` (полный
lifespan), тот же приём, что `test_admin_health.py`.

Проверяется на `GET /health` (публичный, без auth) и `GET /admin/health`
(защищённый) — middleware зарегистрирован один раз на всё приложение и
действует одинаково на обоих.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from dekoder.bootstrap.application import create_application
from dekoder.presentation.api.middleware import CORRELATION_ID_HEADER
from dekoder.shared.config import Settings

_LLM_PROVIDER_BASE_URL = "https://example-aggregator.test/v1"
_LLM_PROVIDER_MODELS_URL = f"{_LLM_PROVIDER_BASE_URL}/models"
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
_QDRANT_COLLECTIONS_URL = "http://localhost:6333/collections"
_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "test-admin-api-key"}

_QDRANT_HEALTHY_BODY = {"result": {"collections": []}, "status": "ok", "time": 0.0}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", _LLM_PROVIDER_BASE_URL)
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}")
    monkeypatch.setenv("ADMIN_HEALTH_CHECK_TIMEOUT", "2.0")
    return Settings()


def _mock_lifespan_collection_exists_check() -> None:
    """Тот же приём, что `test_admin_health.py` — мокаем ensure_collection lifespan-вызов для чистоты лога."""
    respx.get("http://localhost:6333/collections/dekoder_knowledge/exists").mock(
        return_value=httpx.Response(200, json={"result": False, "time": 0.0})
    )
    respx.put("http://localhost:6333/collections/dekoder_knowledge").mock(
        return_value=httpx.Response(200, json={"result": True, "time": 0.0})
    )


def _client(settings: Settings) -> TestClient:
    return TestClient(create_application(settings))


class TestPublicHealthEndpoint:
    @respx.mock
    def test_request_without_header_receives_a_new_correlation_id(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        client = _client(settings)

        with client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "dekoder", "version": "0.1.0"}
        assert response.headers.get(CORRELATION_ID_HEADER)

    @respx.mock
    def test_request_with_header_echoes_the_same_correlation_id(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        client = _client(settings)

        with client:
            response = client.get("/health", headers={CORRELATION_ID_HEADER: "client-supplied-id-123"})

        assert response.status_code == 200
        assert response.headers[CORRELATION_ID_HEADER] == "client-supplied-id-123"

    @respx.mock
    def test_two_requests_without_header_receive_different_correlation_ids(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        client = _client(settings)

        with client:
            first = client.get("/health")
            second = client.get("/health")

        assert first.headers[CORRELATION_ID_HEADER] != second.headers[CORRELATION_ID_HEADER]


class TestAdminRoute:
    @respx.mock
    def test_admin_route_without_header_receives_a_new_correlation_id(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        respx.get(_LLM_PROVIDER_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(200, json=_QDRANT_HEALTHY_BODY))
        client = _client(settings)

        with client:
            response = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 200
        assert response.headers.get(CORRELATION_ID_HEADER)

    @respx.mock
    def test_admin_route_with_header_echoes_the_same_correlation_id(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        respx.get(_LLM_PROVIDER_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(200, json=_QDRANT_HEALTHY_BODY))
        client = _client(settings)

        with client:
            response = client.get(
                "/admin/health",
                headers={**_ADMIN_KEY_HEADER, CORRELATION_ID_HEADER: "admin-request-id-456"},
            )

        assert response.status_code == 200
        assert response.headers[CORRELATION_ID_HEADER] == "admin-request-id-456"

    @respx.mock
    def test_admin_route_auth_failure_still_receives_a_correlation_id(self, settings: Settings) -> None:
        """Middleware выполняется раньше `require_admin_api_key` — заголовок присутствует даже на 401."""
        _mock_lifespan_collection_exists_check()
        client = _client(settings)

        with client:
            response = client.get("/admin/health")

        assert response.status_code == 401
        assert response.headers.get(CORRELATION_ID_HEADER)
