"""
Тесты `application/conversation/ports.py::ConversationRepositories`
(Sprint 5, задача S5-03, ADR-5.5) — подтверждают, что `MemoryRepository`
встроен в существующую группу репозиториев, а не в отдельную
параллельную фабрику.
"""

from __future__ import annotations

import dataclasses

from dekoder.application.conversation.ports import ConversationRepositories
from dekoder.application.memory.ports import MemoryRepository


class TestConversationRepositoriesHasMemoryField:
    def test_memory_field_present_with_correct_type(self) -> None:
        field_names = {field.name: field.type for field in dataclasses.fields(ConversationRepositories)}

        assert "memory" in field_names

    def test_memory_repository_protocol_is_the_declared_type(self) -> None:
        annotations = ConversationRepositories.__annotations__

        assert annotations["memory"] == "MemoryRepository"

    def test_no_second_repositories_factory_type_exists(self) -> None:
        # ADR-5.5: не создаётся вторая фабрика репозиториев параллельно
        # ConversationRepositoriesFactory — MemoryRepository встроен в ту
        # же группу, что и users/conversations/messages/profiles.
        import dekoder.application.conversation.ports as ports_module

        factory_like_names = [name for name in dir(ports_module) if "RepositoriesFactory" in name]
        assert factory_like_names == ["ConversationRepositoriesFactory"]


class TestMemoryRepositoryProtocol:
    def test_is_runtime_checkable_protocol(self) -> None:
        assert hasattr(MemoryRepository, "_is_protocol")
        assert MemoryRepository._is_protocol is True

    def test_structural_conformance_of_a_fake(self) -> None:
        class _Fake:
            async def save(self, record: object) -> object: ...
            async def find_relevant(self, user_id: object, limit: int) -> object: ...
            async def list_confirmed_by_user(self, user_id: object) -> object: ...
            async def get_by_id(self, record_id: object) -> object: ...
            async def update_status(self, record_id: object, status: object, updated_by: str) -> object: ...
            async def delete(self, record_id: object, user_id: object) -> None: ...

        assert isinstance(_Fake(), MemoryRepository)
