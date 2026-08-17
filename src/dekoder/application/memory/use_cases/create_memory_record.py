"""
CreateMemoryRecord — use case, создающий новую запись памяти (Sprint 5,
задача S5-05, ADR-5.8/5.9/5.12).

Используется Telegram-хендлером `/remember` (задача S5-07), который явно
передаёт `status=CONFIRMED, source=USER_EXPLICIT` (ADR-5.9) через
`CreateMemoryRecordCommand` — use case НЕ хардкодит эти значения внутри
себя, они приходят от вызывающего кода.

Как и `ProcessUserMessage` (не как `ClearConversation`/`StartNewConversation`/
`GetActiveProfile`/`SelectProfile`), пользователь создаётся автоматически
(`get_or_create_by_telegram_user_id`) — `/remember` может быть первым
действием пользователя, сохранение факта не должно молча завершаться без
эффекта только потому, что пользователь ещё не отправил `/start`.

Логирует создание через `shared.logging` (ADR-5.12) — без `record.text`,
если `is_sensitive=True` (ADR-5.8): логируются только
`action`/`record_id`/`user_id`/`category`.

Не зависит от SQLAlchemy, ORM-моделей, Telegram SDK или LLM — use case'ы
памяти никогда не вызывают LLM и не обращаются к `PromptBuilder`
(`backlog_5.md` §3 «Ограничения архитектуры»).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import CreateMemoryRecordCommand, CreateMemoryRecordResult
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class CreateMemoryRecordUseCase:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: CreateMemoryRecordCommand) -> CreateMemoryRecordResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(command.telegram_user_id)

            now = datetime.now(UTC)
            record = MemoryRecord(
                id=uuid4(),
                user_id=user.id,
                text=command.text,
                category=command.category,
                source=command.source,
                status=command.status,
                confidence=command.confidence,
                is_sensitive=command.is_sensitive,
                expires_at=command.expires_at,
                updated_by="user",
                created_at=now,
                updated_at=now,
            )
            saved = await repositories.memory.save(record)

            self._log_created(saved)
            return CreateMemoryRecordResult(record=saved)

    @staticmethod
    def _log_created(record: MemoryRecord) -> None:
        if record.is_sensitive:
            _logger.info(
                "memory_record_created",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
            )
        else:
            _logger.info(
                "memory_record_created",
                record_id=str(record.id),
                user_id=str(record.user_id),
                category=record.category.value,
                text=record.text,
            )
