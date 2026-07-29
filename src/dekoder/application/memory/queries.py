"""Запросы и View DTO Memory Service (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.domain.memory.dialogue_entry import MessageRole
from dekoder.shared.domain.identifiers import DialogueEntryId, FactId, UserId


@dataclass(frozen=True)
class GetMemoryFactsQuery:
    user_id: UserId


@dataclass(frozen=True)
class GetDialogueHistoryQuery:
    user_id: UserId
    limit: int


@dataclass(frozen=True)
class MemoryFactView:
    fact_id: FactId
    text: str
    confirmed_at: datetime


@dataclass(frozen=True)
class DialogueEntryView:
    entry_id: DialogueEntryId
    role: MessageRole
    text: str
    created_at: datetime
