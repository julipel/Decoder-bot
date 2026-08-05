"""
ListMemoryRecords — use case, возвращающий подтверждённые записи памяти
пользователя (Sprint 5, задача S5-05).

Используется Telegram-хендлером `/memory` (задача S5-07). Возвращает
только `MemoryRepository.list_confirmed_by_user` (`status = CONFIRMED`)
— список не должен показывать `PENDING`/`REJECTED`, по аналогии с тем,
что в контекст промпта попадают только `CONFIRMED` (§13.5 «Плана
реализации.md»).

Как и `ClearConversation`/`StartNewConversation`/`GetActiveProfile`
(не как `CreateMemoryRecord`), пользователь НЕ создаётся автоматически:
чтение памяти неизвестного пользователя не должно порождать пустую
запись `User` — возвращается пустой список.

Read-only операция — не журналируется (ADR-5.12 требует журналирования
только изменений: создание/подтверждение/отклонение/удаление, не чтения).
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import ListMemoryRecordsCommand, ListMemoryRecordsResult


class ListMemoryRecordsUseCase:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: ListMemoryRecordsCommand) -> ListMemoryRecordsResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return ListMemoryRecordsResult(records=())

            records = await repositories.memory.list_confirmed_by_user(user.id)
            return ListMemoryRecordsResult(records=tuple(records))
