"""SQLite-реализация FactRepositoryPort: черновики и подтверждённые факты (docs/02, §16.3)."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import FactDraftId, FactId, UserId
from dekoder.modules.memory.application.ports import FactRepositoryPort
from dekoder.modules.memory.domain.fact import Fact
from dekoder.modules.memory.domain.fact_draft import FactDraft


class SqliteFactRepository(FactRepositoryPort):
    """Хранит черновики (с ограниченным сроком жизни) и подтверждённые факты в SQLite."""

    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def stage_draft(self, user_id: UserId, text: str) -> FactDraft:
        raise NotImplementedError

    def confirm_draft(self, draft_id: FactDraftId) -> Fact:
        raise NotImplementedError

    def list_confirmed(self, user_id: UserId) -> list[Fact]:
        raise NotImplementedError

    def forget(self, user_id: UserId, fact_id: FactId) -> None:
        raise NotImplementedError
