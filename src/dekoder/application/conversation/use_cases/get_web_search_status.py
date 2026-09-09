"""
GetWebSearchStatus — use case, возвращающий текущее состояние
персонального переключателя веб-поиска (внеспринтовая задача, 2026-09-09).

Используется ТОЛЬКО Telegram-хендлером `/websearch` для отображения
текущего статуса — не `ProcessUserMessage` (тот обращается к
`repositories.web_search` напрямую, тем же приёмом, что и
`GetSelectedModel`/`repositories.model_selection`, ADR-7.7).

Read-only операция — не журналируется.
"""

from __future__ import annotations

from dekoder.application.conversation.dto import GetWebSearchStatusCommand, GetWebSearchStatusResult
from dekoder.application.conversation.ports import ConversationRepositoriesFactory


class GetWebSearchStatus:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: GetWebSearchStatusCommand) -> GetWebSearchStatusResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return GetWebSearchStatusResult(enabled=False)
            enabled = await repositories.web_search.get_enabled(user.id)
            return GetWebSearchStatusResult(enabled=enabled)
