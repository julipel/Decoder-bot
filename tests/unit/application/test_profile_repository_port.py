"""
Тест структурного соответствия `SQLAlchemyProfileRepository` протоколу
`ProfileRepository` (Sprint 3, задача S3-05) — по образцу того, как
`UserRepository`/`ConversationRepository` проверяются в существующих
тестах Sprint 2 (`isinstance(obj, Protocol)` благодаря
`@runtime_checkable`, без обращения к реальной БД).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from dekoder.application.profile.ports import ProfileRepository
from dekoder.infrastructure.persistence.profile_repository import SQLAlchemyProfileRepository


class TestSQLAlchemyProfileRepositoryConformsToPort:
    def test_isinstance_check_against_runtime_checkable_protocol(self) -> None:
        repository = SQLAlchemyProfileRepository(session=AsyncMock())

        assert isinstance(repository, ProfileRepository)

    def test_exposes_all_three_protocol_methods(self) -> None:
        repository = SQLAlchemyProfileRepository(session=AsyncMock())

        assert callable(repository.list_active)
        assert callable(repository.get_active_profile)
        assert callable(repository.select_profile)
