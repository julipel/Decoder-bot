"""MemoryRepository — Dialogue History и Long-term Memory (черновики + факты) одним портом (docs/versions/05, §7)."""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.memory.dialogue_entry import DialogueEntry, MessageRole
from dekoder.domain.memory.fact import MemoryFact
from dekoder.domain.memory.fact_draft import MemoryFactDraft
from dekoder.shared.domain.identifiers import CorrelationId, DraftId, FactId, UserId


class MemoryRepository(Protocol):
    def record_message(
        self, user_id: UserId, role: MessageRole, text: str, correlation_id: CorrelationId
    ) -> DialogueEntry: ...

    def get_recent_history(self, user_id: UserId, limit: int) -> list[DialogueEntry]: ...

    def stage_fact_draft(self, user_id: UserId, text: str) -> MemoryFactDraft: ...

    def confirm_fact_draft(self, draft_id: DraftId) -> MemoryFact: ...

    def list_confirmed_facts(self, user_id: UserId) -> list[MemoryFact]: ...

    def forget_fact(self, user_id: UserId, fact_id: FactId) -> None: ...
