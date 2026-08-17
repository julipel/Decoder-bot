"""
RejectMemoryRecord — use case, переводящий запись памяти в статус
`REJECTED` (Sprint 5, задача S5-05, ADR-5.9/5.12).

Зеркало `ConfirmMemoryRecord` — то же обоснование отсутствия
Telegram-вызывающего сценария в Sprint 5, тот же прецедент (ADR-4.5,
S4-06): реализован полноценно, не заглушкой.

Логирует отклонение через `shared.logging` (ADR-5.12) — без
`record.text`, если `is_sensitive=True` (ADR-5.8).
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import RejectMemoryRecordCommand, RejectMemoryRecordResult
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryStatus
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class RejectMemoryRecordUseCase:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: RejectMemoryRecordCommand) -> RejectMemoryRecordResult:
        async with self._repositories() as repositories:
            existing = await repositories.memory.get_by_id(command.record_id)
            if existing is None:
                return RejectMemoryRecordResult(record=None)

            updated = await repositories.memory.update_status(
                command.record_id, MemoryStatus.REJECTED, command.updated_by
            )
            self._log_rejected(updated)
            return RejectMemoryRecordResult(record=updated)

    @staticmethod
    def _log_rejected(record: MemoryRecord) -> None:
        if record.is_sensitive:
            _logger.info(
                "memory_record_rejected",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
            )
        else:
            _logger.info(
                "memory_record_rejected",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
                text=record.text,
            )
