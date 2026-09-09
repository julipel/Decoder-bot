"""
SetWebSearchEnabled — use case, устанавливающий персональный переключатель
веб-поиска пользователя (внеспринтовая задача, 2026-09-09).

Используется callback-хендлером `/websearch` — единственная операция
записи `user_web_search_settings` во всём проекте.

Как и `SelectModel`, пользователь создаётся автоматически
(`get_or_create_by_telegram_user_id`) — переключатель должен быть
устанавливаем независимо от того, писал ли пользователь что-то раньше.

Логирует изменение через `shared.logging` (по аналогии с `SelectModel`) —
сам факт «включено/выключено» не является чувствительными данными.
"""

from __future__ import annotations

from dekoder.application.conversation.dto import SetWebSearchEnabledCommand, SetWebSearchEnabledResult
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.shared.logging import get_logger, log_audit_event

_logger = get_logger(__name__)


class SetWebSearchEnabled:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: SetWebSearchEnabledCommand) -> SetWebSearchEnabledResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(command.telegram_user_id)
            await repositories.web_search.set_enabled(user.id, command.enabled)
            log_audit_event(_logger, "web_search_setting_changed", user_id=str(user.id), enabled=command.enabled)

        return SetWebSearchEnabledResult(enabled=command.enabled)
