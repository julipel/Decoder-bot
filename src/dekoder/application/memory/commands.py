"""Команды Memory Service (docs/versions/05, §4)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.memory.dialogue_entry import MessageRole
from dekoder.shared.domain.identifiers import CorrelationId, DraftId, FactId, UserId


@dataclass(frozen=True)
class RecordDialogueMessageCommand:
    user_id: UserId
    role: MessageRole
    message_text: str
    correlation_id: CorrelationId


@dataclass(frozen=True)
class StageMemoryFactCommand:
    user_id: UserId
    fact_text: str


@dataclass(frozen=True)
class ConfirmMemoryFactCommand:
    user_id: UserId
    draft_id: DraftId


@dataclass(frozen=True)
class ForgetMemoryFactCommand:
    user_id: UserId
    fact_id: FactId
