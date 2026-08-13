"""
Интеграционные тесты `admin_profiles_router` (Sprint 8, задача S8-08,
ADR-8.8) — через реальный `create_application(settings)` (полный
lifespan, реальная SQLite БД во временном каталоге), тот же приём, что
`test_admin_documents.py`. Схема поднимается через `Base.metadata.
create_all()` (не полный `alembic upgrade head`) — сид-каталог профилей
вставляется вручную (один `is_default=True` профиль, по образцу
`test_profile_repository.py::_seed_catalog`), чтобы проверить сценарий
409 на архивировании дефолт-профиля без зависимости от содержимого
реальной сид-миграции S3-04.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dekoder.bootstrap.application import create_application
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.config import Settings

_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "test-admin-api-key"}


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
def client(settings: Settings) -> TestClient:
    return TestClient(create_application(settings))


def _create_profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Новый профиль",
        "description": "Описание",
        "system_instruction": "Инструкция",
        "response_style": "нейтральный",
        "target_audience": "все",
        "formality_level": "нейтральный",
        "preferred_structure": "без требований",
    }
    payload.update(overrides)
    return payload


class TestProfileCrudLifecycle:
    def test_create_get_patch_archive_list_cycle(self, client: TestClient) -> None:
        with client:
            create_response = client.post(
                "/admin/profiles", headers=_ADMIN_KEY_HEADER, json=_create_profile_payload(name="Служба поддержки")
            )
            assert create_response.status_code == 201
            body = create_response.json()
            assert body["is_default"] is False
            assert body["is_system"] is False
            assert body["status"] == "active"
            profile_id = body["id"]

            get_response = client.get(f"/admin/profiles/{profile_id}", headers=_ADMIN_KEY_HEADER)
            assert get_response.status_code == 200
            assert get_response.json()["name"] == "Служба поддержки"

            patch_response = client.patch(
                f"/admin/profiles/{profile_id}", headers=_ADMIN_KEY_HEADER, json={"name": "Служба поддержки (v2)"}
            )
            assert patch_response.status_code == 200
            patched = patch_response.json()
            assert patched["name"] == "Служба поддержки (v2)"
            # Остальные поля не изменились частичным PATCH.
            assert patched["description"] == "Описание"

            archive_response = client.post(f"/admin/profiles/{profile_id}/archive", headers=_ADMIN_KEY_HEADER)
            assert archive_response.status_code == 200
            assert archive_response.json()["status"] == "archived"

            list_response = client.get("/admin/profiles", headers=_ADMIN_KEY_HEADER)
            assert list_response.status_code == 200
            listed = next(profile for profile in list_response.json() if profile["id"] == profile_id)
            assert listed["status"] == "archived"

    def test_get_unknown_profile_returns_404(self, client: TestClient) -> None:
        with client:
            response = client.get(f"/admin/profiles/{uuid4()}", headers=_ADMIN_KEY_HEADER)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_patch_unknown_profile_returns_404(self, client: TestClient) -> None:
        with client:
            response = client.patch(f"/admin/profiles/{uuid4()}", headers=_ADMIN_KEY_HEADER, json={"name": "x"})

        assert response.status_code == 404

    def test_create_request_cannot_set_is_default_or_is_system_or_status(self, client: TestClient) -> None:
        payload = _create_profile_payload(is_default=True, is_system=True, status="archived")
        with client:
            response = client.post("/admin/profiles", headers=_ADMIN_KEY_HEADER, json=payload)

        assert response.status_code == 201
        body = response.json()
        # Лишние поля payload'а pydantic молча игнорирует (не входят в схему) — профиль создаётся штатно.
        assert body["is_default"] is False
        assert body["is_system"] is False
        assert body["status"] == "active"


class TestArchiveDefaultProfileForbidden:
    """AC-2: попытка архивировать сид-профиль с is_default=True -> 409."""

    def test_archiving_default_profile_returns_409(self, client: TestClient) -> None:
        with client:
            list_response = client.get("/admin/profiles", headers=_ADMIN_KEY_HEADER)
            default_profile = next(profile for profile in list_response.json() if profile["is_default"] is True)

            archive_response = client.post(
                f"/admin/profiles/{default_profile['id']}/archive", headers=_ADMIN_KEY_HEADER
            )

        assert archive_response.status_code == 409
        assert archive_response.json()["error"]["code"] == "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN"

        with client:
            get_response = client.get(f"/admin/profiles/{default_profile['id']}", headers=_ADMIN_KEY_HEADER)
        assert get_response.json()["status"] == "active"


class TestAdminProfilesAuth:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/admin/profiles"),
            ("POST", "/admin/profiles"),
            ("GET", "/admin/profiles/11111111-1111-1111-1111-111111111111"),
            ("PATCH", "/admin/profiles/11111111-1111-1111-1111-111111111111"),
            ("POST", "/admin/profiles/11111111-1111-1111-1111-111111111111/archive"),
        ],
    )
    def test_each_endpoint_rejects_missing_api_key(self, client: TestClient, method: str, path: str) -> None:
        with client:
            response = client.request(method, path)

        assert response.status_code == 401
