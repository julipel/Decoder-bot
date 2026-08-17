"""
Интеграционные тесты `admin_documents_router` (Sprint 8, задача S8-05,
ADR-8.4/8.6) — через реальный `create_application(settings)` (полный
lifespan, реальная SQLite БД во временном каталоге, реальный конвейер
индексации), тот же приём, что `test_application_bootstrap.py`.

Внешние сетевые сервисы:
- OpenAI embeddings — перехватывается `respx` (реальный сетевой вызов
  никогда не происходит, тот же приём, что
  `test_openai_embedding_provider.py`);
- Qdrant — реального сервера в этой тестовой среде нет, поэтому
  `get_qdrant_client` переопределяется через `app.dependency_overrides`
  на `FakeAsyncQdrantClient` (`tests/support/fake_qdrant_client.py`) —
  duck-typed in-memory фейк, принимающий РЕАЛЬНЫЕ объекты
  `qdrant_client.models`, которые строит `QdrantVectorRepository`
  (production-код, не подменяется). Это единственное отличие от «полностью
  реального lifespan» — обосновано отсутствием Qdrant в CI/локальной
  тестовой среде; реальная сквозная проверка с настоящим Qdrant —
  Docker-верификация S8-11.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from tests.support.fake_qdrant_client import FakeAsyncQdrantClient

from dekoder.bootstrap.application import create_application, get_qdrant_client
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.shared.config import Settings

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "test-admin-api-key"}


@pytest.fixture
async def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("KNOWLEDGE_STORAGE_PATH", str(tmp_path / "knowledge_documents"))
    # `create_application()`'s lifespan только подключается к БД (S2-01),
    # схему создаёт Alembic — здесь, как и в
    # `test_knowledge_document_repository.py`, схема поднимается напрямую
    # через `Base.metadata.create_all` на отдельном engine, эквивалентно
    # `alembic upgrade head` для целей этого теста (не тестируем сами
    # миграции здесь — для этого есть `test_migrations.py`).
    schema_engine = create_database_engine(database_url)
    async with schema_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await schema_engine.dispose()
    return Settings()


def _mock_embeddings_route() -> respx.Route:
    def _respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = payload["input"]
        return httpx.Response(
            200,
            json={
                "data": [{"index": index, "embedding": [0.1, 0.2, 0.3]} for index in range(len(texts))],
                "model": "text-embedding-3-small",
            },
        )

    return respx.post(_EMBEDDINGS_URL).mock(side_effect=_respond)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_application(settings)
    fake_qdrant_client = FakeAsyncQdrantClient()
    app.dependency_overrides[get_qdrant_client] = lambda: fake_qdrant_client
    return TestClient(app)


class TestDocumentLifecycle:
    @respx.mock
    def test_upload_list_get_delete_cycle(self, client: TestClient) -> None:
        _mock_embeddings_route()

        with client:
            upload_response = client.post(
                "/admin/documents",
                headers=_ADMIN_KEY_HEADER,
                files={"file": ("note.txt", b"Some content for indexing.", "text/plain")},
                data={"title": "Заметка"},
            )
            assert upload_response.status_code == 201
            body = upload_response.json()
            assert body["status"] == "indexed"
            assert body["title"] == "Заметка"
            assert "checksum" not in body
            document_id = body["id"]

            list_response = client.get("/admin/documents", headers=_ADMIN_KEY_HEADER)
            assert list_response.status_code == 200
            assert any(document["id"] == document_id for document in list_response.json())

            get_response = client.get(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert get_response.status_code == 200
            assert get_response.json()["id"] == document_id
            assert get_response.json()["status"] == "indexed"

            delete_response = client.delete(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert delete_response.status_code == 204

            get_after_delete = client.get(f"/admin/documents/{document_id}", headers=_ADMIN_KEY_HEADER)
            assert get_after_delete.status_code == 404
            assert get_after_delete.json()["error"]["code"] == "NOT_FOUND"

    def test_delete_unknown_document_is_idempotent(self, client: TestClient) -> None:
        with client:
            response = client.delete("/admin/documents/11111111-1111-1111-1111-111111111111", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 204

    @respx.mock
    def test_reindex_preserves_document_id_and_recomputes_chunk_count(self, client: TestClient) -> None:
        _mock_embeddings_route()

        with client:
            upload_response = client.post(
                "/admin/documents",
                headers=_ADMIN_KEY_HEADER,
                files={"file": ("note.txt", b"Content for reindex test.", "text/plain")},
            )
            document_id = upload_response.json()["id"]

            reindex_response = client.post(f"/admin/documents/{document_id}/reindex", headers=_ADMIN_KEY_HEADER)

        assert reindex_response.status_code == 200
        assert reindex_response.json()["id"] == document_id
        assert reindex_response.json()["status"] == "indexed"

    def test_reindex_of_unknown_document_returns_404(self, client: TestClient) -> None:
        with client:
            response = client.post(
                "/admin/documents/11111111-1111-1111-1111-111111111111/reindex", headers=_ADMIN_KEY_HEADER
            )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


class TestAdminDocumentsAuth:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/admin/documents"),
            ("GET", "/admin/documents"),
            ("GET", "/admin/documents/11111111-1111-1111-1111-111111111111"),
            ("DELETE", "/admin/documents/11111111-1111-1111-1111-111111111111"),
            ("POST", "/admin/documents/11111111-1111-1111-1111-111111111111/reindex"),
        ],
    )
    def test_each_endpoint_rejects_missing_api_key(self, client: TestClient, method: str, path: str) -> None:
        with client:
            response = client.request(method, path)

        assert response.status_code == 401
