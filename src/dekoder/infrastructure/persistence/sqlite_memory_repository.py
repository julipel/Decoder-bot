from __future__ import annotations

from dekoder.application.memory.ports import MemoryRepository
from dekoder.domain.memory.dialogue_entry import DialogueEntry, MessageRole
from dekoder.domain.memory.fact import MemoryFact
from dekoder.domain.memory.fact_draft import MemoryFactDraft
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import CorrelationId, DraftId, FactId, UserId


class SqliteMemoryRepository(MemoryRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def record_message(
        self, user_id: UserId, role: MessageRole, text: str, correlation_id: CorrelationId
    ) -> DialogueEntry:
        raise NotImplementedError

    def get_recent_history(self, user_id: UserId, limit: int) -> list[DialogueEntry]:
        raise NotImplementedError

    def stage_fact_draft(self, user_id: UserId, text: str) -> MemoryFactDraft:
        raise NotImplementedError

    def confirm_fact_draft(self, draft_id: DraftId) -> MemoryFact:
        raise NotImplementedError

    def list_confirmed_facts(self, user_id: UserId) -> list[MemoryFact]:
        raise NotImplementedError

    def forget_fact(self, user_id: UserId, fact_id: FactId) -> None:
        raise NotImplementedError
