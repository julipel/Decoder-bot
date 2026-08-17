"""
`UpdateProfile` — частичное обновление профиля (`PATCH`, Sprint 8,
задача S8-07, ADR-8.7/8.8).

`is_system`/`is_default`/`status` не входят в `UpdateProfileCommand`
физически (`application/profile/dto.py`) — их невозможно изменить через
этот use case ни при каких значениях команды. `dataclasses.replace()`
поверх уже существующего профиля — идиоматично для `frozen`-датаклассов
(`UserProfile`, ADR-3.5). `None` — штатный отрицательный исход
(`profile_id` не существует), не исключение.

Логирует `admin_profile_updated` (ADR-8.10) — только `profile_id`, без
изменённых полей/текста профиля.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import UpdateProfileCommand
from dekoder.domain.profile.entities import UserProfile
from dekoder.shared.logging import get_logger, log_audit_event

_logger = get_logger(__name__)


class UpdateProfile:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: UpdateProfileCommand) -> UserProfile | None:
        async with self._repositories() as repositories:
            existing = await repositories.profiles.get_by_id(command.profile_id)
            if existing is None:
                return None

            # dataclasses.replace() типизирован mypy пофielно — динамический
            # набор ключей из changed_fields() (dict[str, object]) в
            # принципе не может быть проверен статически для каждого поля
            # по отдельности; корректность обеспечивается тем, что все ключи
            # changed_fields() — реальные имена полей UserProfile (см. тело
            # метода в application/profile/dto.py), исключая
            # is_system/is_default/status.
            updated = replace(existing, **command.changed_fields(), updated_at=datetime.now(UTC))  # type: ignore[arg-type]
            saved = await repositories.profiles.update(updated)
            log_audit_event(_logger, "admin_profile_updated", profile_id=str(saved.id))
            return saved
