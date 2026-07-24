"""
Канало-независимое представление сообщения (docs/02, §2 — домен Message).

Единственный контракт, который должен знать любой driving adapter
(Telegram, в будущем — голос или другой канал), поэтому типы намеренно
не содержат ничего специфичного для конкретного канала.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import ChatId, CorrelationId, UserId


@dataclass(frozen=True)
class IncomingMessage:
    """Входящее сообщение пользователя, полученное через любой канал."""

    user_id: UserId
    chat_id: ChatId
    text: str
    command: str | None
    correlation_id: CorrelationId


@dataclass(frozen=True)
class OutgoingResponse:
    """Ответ AI Core; driving adapter преобразует его в формат своего канала."""

    text: str
    requires_confirmation: bool = False
    confirmation_action: str | None = None
