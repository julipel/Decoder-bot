"""
Интеграционные тесты `admin_ui_router` (`GET /admin/ui/documents`) —
внеспринтовая фича, см. claude.md §32.

Проверяет ровно то, что документировано как намеренное исключение в
`presentation/api/routes/admin_ui.py`: страница отдаётся БЕЗ
`X-Admin-Api-Key` (сама разметка не содержит данных), но при этом ссылается
на защищённый REST API правильным путём — фактическая защита остаётся на
`admin_documents_router`, покрытом отдельно в `test_admin_documents.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dekoder.bootstrap.application import create_application
from dekoder.shared.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "test-embedding-api-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-api-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test-app.db'}")
    return Settings()


def _client(settings: Settings) -> TestClient:
    return TestClient(create_application(settings))


class TestAdminDocumentsUiPage:
    def test_returns_200_without_admin_api_key(self, settings: Settings) -> None:
        client = _client(settings)

        with client:
            response = client.get("/admin/ui/documents")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_page_references_protected_documents_api(self, settings: Settings) -> None:
        client = _client(settings)

        with client:
            response = client.get("/admin/ui/documents")

        assert "/admin/documents" in response.text
        assert "X-Admin-Api-Key" in response.text
