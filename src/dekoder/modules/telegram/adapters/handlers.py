"""
Обработчики обновлений Telegram: только преобразование форматов (Telegram
update → IncomingMessage, OutgoingResponse → ответ Telegram), без
бизнес-логики (docs/02, §5).
"""

from __future__ import annotations

from dekoder.modules.ai_core.application.ports import ConversationPort
from dekoder.modules.ai_core.domain.message import IncomingMessage, OutgoingResponse
from dekoder.modules.logging_audit.application.ports import LoggerPort


class TelegramUpdateHandler:
    def __init__(self, conversation: ConversationPort, logger: LoggerPort) -> None:
        self._conversation = conversation
        self._logger = logger

    def handle_update(self, raw_update: dict) -> None:
        """Строит IncomingMessage из сырого обновления Telegram и вызывает ConversationPort."""
        raise NotImplementedError

    def _to_incoming_message(self, raw_update: dict) -> IncomingMessage:
        raise NotImplementedError

    def _send_response(self, chat_id: str, response: OutgoingResponse) -> None:
        raise NotImplementedError
