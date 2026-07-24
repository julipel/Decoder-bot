"""
Отдельная реплика диалога (docs/01, §4.4).

Реплика пользователя и ответ ассистента — два разных DialogueMessage, а
не одна запись, которая сначала создаётся с текстом пользователя, а потом
дополняется текстом ответа. Статус обработки запроса (received/completed/
failed) относится к реплике пользователя — см. docs/03, §16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dekoder.shared.domain.identifiers import ChatId, CorrelationId, DialogueMessageId


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class RequestProcessingStatus(str, Enum):
    """Статус обработки запроса, связанного с репликой пользователя (docs/02, §8)."""

    RECEIVED = "received"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DialogueMessage:
    """Одна реплика диалога — пользователя или ассистента."""

    message_id: DialogueMessageId
    dialogue_id: ChatId
    role: MessageRole
    text: str
    created_at: datetime
    correlation_id: CorrelationId
    processing_status: RequestProcessingStatus | None = None
    """Заполняется только для реплик пользователя (role=USER); у ответов ассистента — None."""
