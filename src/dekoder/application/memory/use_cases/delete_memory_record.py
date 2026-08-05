"""
DeleteMemoryRecord — use case, удаляющий запись памяти пользователя
(Sprint 5, задача S5-05, ADR-5.10/5.12).

Используется `MemoryDeleteCallbackHandler` (задача S5-07, inline-кнопка
🗑 в `/memory`) — `command.telegram_user_id` берётся из
`update.callback_query.from_user`, НЕ `update.effective_user` (ADR-5.10).

Идемпотентна (по прецеденту `MessageRepository.clear`): удаление
несуществующей записи или записи другого пользователя не поднимает
ошибку — `repositories.memory.delete(record_id, user_id)` уже проверяет
владельца на уровне репозитория (ADR-5.10, «не полагаться только на то,
что кнопку видит только владелец»); этот use case не полагается на
Telegram UI как единственную защиту.

Логирует удаление через `shared.logging` (ADR-5.12) только тогда, когда
запись действительно существовала и принадлежала вызывающему
пользователю — без `record.text`, если `is_sensitive=True` (ADR-5.8).
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import DeleteMemoryRecordCommand
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class DeleteMemoryRecordUseCase:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: DeleteMemoryRecordCommand) -> None:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                # Идемпотентно: неизвестный пользователь — нечего удалять.
                return

            existing = await repositories.memory.get_by_id(command.record_id)
            await repositories.memory.delete(command.record_id, user.id)

            if existing is None or existing.user_id != user.id:
                # Идемпотентно: записи не было или она принадлежала
                # другому пользователю — delete() ничего не удалил,
                # событие "удалено" не журналируется.
                return

            self._log_deleted(existing)

    @staticmethod
    def _log_deleted(record: MemoryRecord) -> None:
        if record.is_sensitive:
            _logger.info(
                "memory_record_deleted",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
            )
        else:
            _logger.info(
                "memory_record_deleted",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
                text=record.text,
            )
