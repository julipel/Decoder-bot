"""
ListProfiles — use case, возвращающий весь общий сид-каталог активных
профилей (Sprint 3, задача S3-06).

Используется будущим обработчиком команды `/profile` (задача S3-08).
Не зависит от `telegram_user_id` — каталог общий для всех пользователей
(backlog_3.md §1), поэтому `execute()` не принимает команду.

Зависит от `ConversationRepositoriesFactory` (`application/conversation/
ports.py`) — того же порта, каким `StartNewConversation`/
`ClearConversation` получают короткоживущую транзакцию; используется
только поле `repositories.profiles`, остальные (`users`/`conversations`/
`messages`) этим use case'ом не вызываются вовсе — по тому же принципу,
что и `StartNewConversation`, использующий только нужные ему поля общей
группы репозиториев (ADR-3.3).

Не зависит от SQLAlchemy, ORM-моделей или Telegram SDK.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import ListProfilesResult


class ListProfiles:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self) -> ListProfilesResult:
        async with self._repositories() as repositories:
            profiles = await repositories.profiles.list_active()
            return ListProfilesResult(profiles=tuple(profiles))
