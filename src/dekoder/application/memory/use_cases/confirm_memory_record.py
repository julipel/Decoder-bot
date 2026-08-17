"""
ConfirmMemoryRecord — use case, переводящий запись памяти в статус
`CONFIRMED` (Sprint 5, задача S5-05, ADR-5.9/5.12).

Не имеет вызывающего Telegram-сценария в Sprint 5 (`/remember` создаёт
запись сразу `CONFIRMED`, ADR-5.9) — реализован полноценно, не заглушкой,
задел на будущий подтверждаемый сценарий (например, гипотетические
AI-предложения фактов, которые пользователь/администратор подтверждает),
по тому же прецеденту, что тиры 4/5 `TokenBudgetPolicy` (ADR-4.5, S4-06).

Не привязан к `telegram_user_id`: неизвестно, какой каталог вызывающих
сценариев появится в будущем (Telegram/админ-интерфейс/что-то ещё) —
`ConfirmMemoryRecordCommand` принимает `record_id`/`updated_by` напрямую.

Логирует подтверждение через `shared.logging` (ADR-5.12) — без
`record.text`, если `is_sensitive=True` (ADR-5.8).
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import ConfirmMemoryRecordCommand, ConfirmMemoryRecordResult
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryStatus
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class ConfirmMemoryRecordUseCase:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: ConfirmMemoryRecordCommand) -> ConfirmMemoryRecordResult:
        async with self._repositories() as repositories:
            existing = await repositories.memory.get_by_id(command.record_id)
            if existing is None:
                return ConfirmMemoryRecordResult(record=None)

            updated = await repositories.memory.update_status(
                command.record_id, MemoryStatus.CONFIRMED, command.updated_by
            )
            self._log_confirmed(updated)
            return ConfirmMemoryRecordResult(record=updated)

    @staticmethod
    def _log_confirmed(record: MemoryRecord) -> None:
        if record.is_sensitive:
            _logger.info(
                "memory_record_confirmed",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
            )
        else:
            _logger.info(
                "memory_record_confirmed",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
                text=record.text,
            )
