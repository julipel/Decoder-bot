"""
DialogueEntry — одна реплика диалога; неизменна после создания, не
редактируется и не удаляется (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dekoder.shared.domain.identifiers import CorrelationId, DialogueEntryId, UserId


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class RequestProcessingStatus(str, Enum):
    RECEIVED = "received"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DialogueEntry:
    entry_id: DialogueEntryId
    user_id: UserId
    role: MessageRole
    text: str
    created_at: datetime
    correlation_id: CorrelationId
    processing_status: RequestProcessingStatus | None = None
