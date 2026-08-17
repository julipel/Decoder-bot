"""
GetActiveProfile — use case, возвращающий активный профиль пользователя
(Sprint 3, задача S3-06).

Используется будущим обработчиком команды `/profile` (задача S3-08) —
для отображения текущего активного профиля перед показом клавиатуры
выбора — и другими сценариями, которым нужно узнать активный профиль
пользователя без изменения выбора.

Зависит от `ConversationRepositoriesFactory` — тот же порт, что и у
`ListProfiles`/`SelectProfile`. Как и `StartNewConversation`/
`ClearConversation` (Sprint 2, задачи S2-07/S2-09), пользователь НЕ
создаётся автоматически: используется `UserRepository.
get_by_telegram_user_id` (не `get_or_create_by_telegram_user_id`) — если
пользователь неизвестен, use case возвращает
`GetActiveProfileResult(profile=None)`, штатный, не ошибочный исход.

Не зависит от SQLAlchemy, ORM-моделей или Telegram SDK.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import GetActiveProfileCommand, GetActiveProfileResult


class GetActiveProfile:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: GetActiveProfileCommand) -> GetActiveProfileResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return GetActiveProfileResult(profile=None)

            profile = await repositories.profiles.get_active_profile(user.id)
            return GetActiveProfileResult(profile=profile)
