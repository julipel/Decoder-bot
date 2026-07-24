"""SQLite-реализация DialogueHistoryPort (docs/02, §8, §14 — текст диалога отдельно от технического журнала)."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import ChatId, CorrelationId, DialogueMessageId
from dekoder.modules.memory.application.ports import DialogueHistoryPort
from dekoder.modules.memory.domain.dialogue_message import DialogueMessage


class SqliteDialogueHistoryRepository(DialogueHistoryPort):
    """
    Хранит реплики диалога в отдельной таблице SQLite — по одной записи на
    реплику пользователя и на ответ ассистента (docs/03, §16). Создание
    таблиц — вне объёма задачи.
    """

    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get_recent(self, dialogue_id: ChatId, limit: int) -> list[DialogueMessage]:
        raise NotImplementedError

    def record_user_message(
        self, dialogue_id: ChatId, text: str, correlation_id: CorrelationId
    ) -> DialogueMessage:
        raise NotImplementedError

    def record_assistant_message(
        self, dialogue_id: ChatId, text: str, correlation_id: CorrelationId
    ) -> DialogueMessage:
        raise NotImplementedError

    def mark_request_completed(self, user_message_id: DialogueMessageId) -> None:
        raise NotImplementedError

    def mark_request_failed(self, user_message_id: DialogueMessageId) -> None:
        raise NotImplementedError
