"""
Сквозной сценарий Sprint 8 (задача S8-11, «Финальная интеграция и
E2E-проверка Sprint 8») — весь admin REST-слой через один реальный
`create_application(settings)` (полный lifespan), по образцу
`tests/e2e/test_profile_scenario.py`/S3-09.

Один continuous-сценарий, не изолированные кусочки — доказывает, что три
admin-роутера (`admin_documents_router`/`admin_profiles_router`/
`admin_health_router`), их зависимости (`presentation/api/dependencies/
documents.py`, S8-05) и `ApplicationContainer` (S8-07/S8-09) реально
работают вместе через один и тот же `app`/lifespan, не только по
отдельности (уже покрыто `test_admin_documents.py`/`test_admin_profiles.py`/
`test_admin_health.py`).

Внешние сервисы: OpenAI embeddings/дженерик LLM-провайдер/OpenAI `/models` —
`respx`; Qdrant — `FakeAsyncQdrantClient` через
`app.dependency_overrides[get_qdrant_client]` для документного конвейера
(работает для `presentation/api/dependencies/documents.py`, per-request
DI) и отдельно `respx`-перехват реального REST `GET /collections` для
`GET /admin/health` (не per-request DI, см. докстринг
`test_admin_health.py`) — оба подхода используются одновременно в одном
тесте.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from tests.support.fake_qdrant_client import FakeAsyncQdrantClient

from dekoder.bootstrap.application import create_application, get_qdrant_client
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.config import Settings

_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "e2e-admin-api-key"}
_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_LLM_PROVIDER_BASE_URL = "https://example-aggregator.test/v1"
_LLM_PROVIDER_MODELS_URL = f"{_LLM_PROVIDER_BASE_URL}/models"
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
_QDRANT_COLLECTIONS_URL = "http://localhost:6333/collections"
_QDRANT_COLLECTION_EXISTS_URL = "http://localhost:6333/collections/dekoder_knowledge/exists"


def _profile_orm(*, name: str, is_default: bool) -> ProfileORM:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    return ProfileORM(
        id=uuid4(),
        name=name,
        description="Описание",
        system_instruction="Инструкция",
        response_style="нейтральный",
        target_audience="все",
        formality_level="нейтральный",
        preferred_structure="без требований",
        forbidden_phrasing=[],
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status="active",
        is_system=True,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "e2e-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "e2e-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "e2e-llm-provider-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", _LLM_PROVIDER_BASE_URL)
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "e2e-openai-key")
    monkeypatch.setenv("ADMIN_API_KEY", "e2e-admin-api-key")
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-admin.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("KNOWLEDGE_STORAGE_PATH", str(tmp_path / "knowledge_documents"))

    schema_engine = create_database_engine(database_url)
    async with schema_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(schema_engine)
    default_profile = _profile_orm(name="Дефолт", is_default=True)
    async with session_factory() as session:
        session.add(default_profile)
        await session.commit()
    await schema_engine.dispose()

    return Settings()


@pytest.fixture
def fake_qdrant_client() -> FakeAsyncQdrantClient:
    return FakeAsyncQdrantClient()


@pytest.fixture
def client(settings: Settings, fake_qdrant_client: FakeAsyncQdrantClient) -> TestClient:
    app = create_application(settings)
    app.dependency_overrides[get_qdrant_client] = lambda: fake_qdrant_client
    return TestClient(app)


def _mock_embeddings_route() -> None:
    def _respond(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": [0.1, 0.2, 0.3]} for i in range(len(texts))]}
        )

    respx.post(_EMBEDDINGS_URL).mock(side_effect=_respond)


def _mock_lifespan_qdrant_setup() -> None:
    respx.get(_QDRANT_COLLECTION_EXISTS_URL).mock(return_value=httpx.Response(200, json={"result": False, "time": 0.0}))
    respx.put("http://localhost:6333/collections/dekoder_knowledge").mock(
        return_value=httpx.Response(200, json={"result": True, "time": 0.0})
    )


class TestAuthEnforcedOnAllThreeRouters:
    """Запрос без X-Admin-Api-Key -> 401 на каждом из трёх роутеров (документы/профили/health)."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/admin/documents"),
            ("GET", "/admin/profiles"),
            ("GET", "/admin/health"),
        ],
    )
    def test_missing_key_rejected_everywhere(self, client: TestClient, method: str, path: str) -> None:
        with client:
            response = client.request(method, path)

        assert response.status_code == 401

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/admin/documents"),
            ("GET", "/admin/profiles"),
            ("GET", "/admin/health"),
        ],
    )
    def test_wrong_key_rejected_everywhere(self, client: TestClient, method: str, path: str) -> None:
        with client:
            response = client.request(method, path, headers={"X-Admin-Api-Key": "wrong-key"})

        assert response.status_code == 401


class TestFullAdminVerticalSlice:
    """Один continuous-прогон: документы + профили + health через один и тот же app/lifespan."""

    @respx.mock
    def test_document_lifecycle_profile_lifecycle_and_health_in_one_run(self, client: TestClient) -> None:
        _mock_lifespan_qdrant_setup()
        _mock_embeddings_route()

        with client:
            # --- 1. Document lifecycle: upload -> list -> get -> reindex -> delete -> 404 ---
            upload = client.post(
                "/admin/documents",
                headers=_ADMIN_KEY_HEADER,
                files={"file": ("note.txt", b"E2E admin scenario content.", "text/plain")},
                data={"title": "E2E документ"},
            )
            assert upload.status_code == 201
            document = upload.json()
            assert document["status"] == "indexed"
            document_id = document["id"]

            listed = client.get("/admin/documents", headers=_ADMIN_KEY_HEADER)
            assert listed.status_code == 200
            assert any(d["id"] == document_id for d in listed.json())

            fetched = client.get(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert fetched.status_code == 200

            reindexed = client.post(f"/admin/documents/{document_id}/reindex", headers=_ADMIN_KEY_HEADER)
            assert reindexed.status_code == 200
            assert reindexed.json()["id"] == document_id

            deleted = client.delete(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert deleted.status_code == 204

            gone = client.get(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert gone.status_code == 404

            # --- 2. Profile lifecycle: create -> patch -> archive; default profile archive -> 409 ---
            created = client.post(
                "/admin/profiles",
                headers=_ADMIN_KEY_HEADER,
                json={
                    "name": "E2E профиль",
                    "description": "d",
                    "system_instruction": "i",
                    "response_style": "нейтральный",
                    "target_audience": "все",
                    "formality_level": "нейтральный",
                    "preferred_structure": "без требований",
                },
            )
            assert created.status_code == 201
            profile = created.json()
            assert profile["is_default"] is False
            assert profile["is_system"] is False
            profile_id = profile["id"]

            patched = client.patch(
                f"/admin/profiles/{profile_id}", headers=_ADMIN_KEY_HEADER, json={"name": "E2E профиль (v2)"}
            )
            assert patched.status_code == 200
            assert patched.json()["name"] == "E2E профиль (v2)"

            archived = client.post(f"/admin/profiles/{profile_id}/archive", headers=_ADMIN_KEY_HEADER)
            assert archived.status_code == 200
            assert archived.json()["status"] == "archived"

            all_profiles = client.get("/admin/profiles", headers=_ADMIN_KEY_HEADER).json()
            default_profile = next(p for p in all_profiles if p["is_default"] is True)

            default_archive_attempt = client.post(
                f"/admin/profiles/{default_profile['id']}/archive", headers=_ADMIN_KEY_HEADER
            )
            assert default_archive_attempt.status_code == 409
            assert default_archive_attempt.json()["error"]["code"] == "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN"

            # --- 3. Health check: healthy scenario within the same run ---
            respx.get(_LLM_PROVIDER_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
            respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
            respx.get(_QDRANT_COLLECTIONS_URL).mock(
                return_value=httpx.Response(200, json={"result": {"collections": []}, "status": "ok", "time": 0.0})
            )
            healthy = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)
            assert healthy.status_code == 200
            assert healthy.json()["all_healthy"] is True

            # --- 4. Health check: unhealthy scenario, still within the same run ---
            respx.get(_LLM_PROVIDER_MODELS_URL).mock(return_value=httpx.Response(503))
            respx.get(_OPENAI_MODELS_URL).mock(return_value=httpx.Response(503))
            respx.get(_QDRANT_COLLECTIONS_URL).mock(return_value=httpx.Response(503))
            unhealthy = client.get("/admin/health", headers=_ADMIN_KEY_HEADER)
            assert unhealthy.status_code == 200
            assert unhealthy.json()["all_healthy"] is False


class TestRegressionOfDialoguePathThroughSameApp:
    """AC-2 (сопутствующее): GET /health (публичный, диалоговый путь) не задет присутствием admin-роутеров."""

    def test_public_health_endpoint_unaffected_by_admin_routers(self, client: TestClient) -> None:
        with client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "dekoder", "version": "0.1.0"}
