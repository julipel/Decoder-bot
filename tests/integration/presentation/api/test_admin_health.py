"""
Интеграционные тесты `GET /admin/health` (Sprint 8, задача S8-09,
ADR-8.9) — через реальный `create_application(settings)` (полный
lifespan), тот же приём, что `test_admin_documents.py`.

Все три внешних сервиса перехватываются `respx`: OpenRouter/OpenAI
`/models` — обычные HTTP-роуты; Qdrant — `GET /collections` (реальный
REST-эндпоинт, который `AsyncQdrantClient.get_collections()` вызывает
под капотом через `httpx`, задействованный `QdrantHealthCheck`,
ADR-8.9). `app.dependency_overrides[get_qdrant_client]` здесь НЕ
работает для целей health-check: `ApplicationContainer.
check_external_services_health` собирается один раз в `_lifespan` поверх
клиента, созданного там же (`build_qdrant_client`), а не через
per-request FastAPI DI (в отличие от `presentation/api/dependencies/
documents.py`, ADR-8.4) — поэтому единственный способ подменить Qdrant
для ЭТОГО эндпоинта в тестах без реального сервера — перехватить его
HTTP-трафик.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from dekoder.bootstrap.application import create_application
from dekoder.shared.config import Settings

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
_QDRANT_COLLECTIONS_URL = "http://localhost:6333/collections"
_QDRANT_COLLECTION_EXISTS_URL = "http://localhost:6333/collections/dekoder_knowledge/exists"
_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "test-admin-api-key"}

_QDRANT_HEALTHY_BODY = {"result": {"collections": []}, "status": "ok", "time": 0.0}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}")
    monkeypatch.setenv("ADMIN_HEALTH_CHECK_TIMEOUT", "2.0")
    return Settings()


def _mock_lifespan_collection_exists_check() -> None:
    """
    `bootstrap/application.py::_lifespan` вызывает `ensure_collection`
    (не fail-fast) на каждом старте — без мока этого эндпоинта тест
    по-прежнему проходит (ошибка только логируется), но лог засоряется
    "not mocked" при активном `respx.mock`; мокаем явно для чистоты.
    """
    respx.get(_QDRANT_COLLECTION_EXISTS_URL).mock(return_value=httpx.Response(200, json={"result": False, "time": 0.0}))
    respx.put("http://localhost:6333/collections/dekoder_knowledge").mock(
        return_value=httpx.Response(200, json={"result": True, "time": 0.0})
    )


def _client(settings: Settings) -> TestClient:
    return TestClient(create_application(settings))


class TestAllServicesHealthy:
    @respx.mock
    def test_returns_200_with_all_healthy_true(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        respx.get(_OPENROUTER_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(200, json=_QDRANT_HEALTHY_BODY))
        client = _client(settings)

        with client:
            response = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 200
        body = response.json()
        assert body["all_healthy"] is True
        assert len(body["services"]) == 3
        assert all(service["healthy"] for service in body["services"])
        assert {service["name"] for service in body["services"]} == {"qdrant", "openrouter", "openai"}


class TestAllServicesUnavailable:
    @respx.mock
    def test_returns_200_with_all_healthy_false_not_5xx(self, settings: Settings) -> None:
        """AC-1: недоступность внешних сервисов -> 200, all_healthy=false — не 5xx."""
        _mock_lifespan_collection_exists_check()
        respx.get(_OPENROUTER_MODELS_URL).mock(return_value=httpx.Response(503))
        respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(503))
        respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(503))
        client = _client(settings)

        with client:
            response = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 200
        body = response.json()
        assert body["all_healthy"] is False
        assert len(body["services"]) == 3
        assert all(not service["healthy"] for service in body["services"])
        assert all(service["detail"] is not None for service in body["services"])


class TestMixedAvailability:
    @respx.mock
    def test_partial_unavailability_reflected_per_service(self, settings: Settings) -> None:
        _mock_lifespan_collection_exists_check()
        respx.get(_OPENROUTER_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(500))
        respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(200, json=_QDRANT_HEALTHY_BODY))
        client = _client(settings)

        with client:
            response = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 200
        body = response.json()
        assert body["all_healthy"] is False
        by_name = {service["name"]: service["healthy"] for service in body["services"]}
        assert by_name["qdrant"] is True
        assert by_name["openrouter"] is True
        assert by_name["openai"] is False


class TestAdminHealthAuth:
    def test_missing_api_key_returns_401(self, settings: Settings) -> None:
        client = _client(settings)

        with client:
            response = client.get("/admin/health")

        assert response.status_code == 401


class TestPublicHealthEndpointUnaffected:
    """AC-2: GET /health не регрессировал (контракт уже покрыт test_health_endpoint.py)."""

    def test_public_health_endpoint_still_responds_without_auth(self, settings: Settings) -> None:
        client = _client(settings)

        with client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "dekoder", "version": "0.1.0"}
