"""
SelectProfile — use case, переключающий активный профиль пользователя
(Sprint 3, задача S3-06).

Используется будущим обработчиком callback'а inline-клавиатуры `/profile`
(задача S3-08) — единственная операция записи каталога/выбора во всём
Sprint 3 (backlog_3.md §3, «Ограничения объёма CRUD»): изменяет только
связь «пользователь → активный профиль» (`user_active_profiles`), не сам
профиль.

Зависит от `ConversationRepositoriesFactory` — тот же порт, что и у
`ListProfiles`/`GetActiveProfile`. Как и `GetActiveProfile`, пользователь
НЕ создаётся автоматически: `UserRepository.get_by_telegram_user_id`
(не `get_or_create_by_telegram_user_id`) — если пользователь неизвестен,
use case возвращает `SelectProfileResult(status=UNKNOWN_USER,
profile=None)`, штатный, не ошибочный исход.

Неизвестный/неактивный `profile_id` — тоже штатный отрицательный исход,
не исключение: `repositories.profiles.select_profile(...)` возвращает
`None`, use case транслирует это в `SelectProfileResult(status=
UNKNOWN_PROFILE, profile=None)`, ничего не изменив (проверка целостности
уже выполнена `SQLAlchemyProfileRepository.select_profile`, задача
S3-05).

Не зависит от SQLAlchemy, ORM-моделей или Telegram SDK.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import SelectProfileCommand, SelectProfileResult, SelectProfileStatus


class SelectProfile:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: SelectProfileCommand) -> SelectProfileResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return SelectProfileResult(status=SelectProfileStatus.UNKNOWN_USER, profile=None)

            selected_profile = await repositories.profiles.select_profile(user.id, command.profile_id)
            if selected_profile is None:
                return SelectProfileResult(status=SelectProfileStatus.UNKNOWN_PROFILE, profile=None)

            return SelectProfileResult(status=SelectProfileStatus.SELECTED, profile=selected_profile)
