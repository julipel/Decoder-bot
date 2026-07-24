"""
Входной порт AI Core (docs/02, §7).

ConversationPort — единственная точка входа в бизнес-логику ассистента.
Любой driving adapter зависит только от этого порта и от типов из
ai_core.domain.message.
"""

from __future__ import annotations

from typing import Protocol

from dekoder.modules.ai_core.domain.message import IncomingMessage, OutgoingResponse


class ConversationPort(Protocol):
    """Обрабатывает входящее сообщение и возвращает ответ пользователю."""

    def handle(self, message: IncomingMessage) -> OutgoingResponse: ...
