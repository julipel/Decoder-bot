"""
`CreateProfile` — создаёт новый профиль каталога (Sprint 8, задача
S8-07, ADR-8.7/8.8).

Всегда создаёт профиль с `is_system=False, is_default=False,
status=ProfileStatus.ACTIVE` — эти три поля не принимаются из
`CreateProfileCommand` (`application/profile/dto.py`), устраняя весь
риск нарушения `uq_profiles_is_default` (частичный уникальный индекс
«не более одного дефолта»): новый профиль никогда не претендует на
дефолт.

Поверх той же `ConversationRepositoriesFactory`, что и `ListProfiles`/
`GetActiveProfile`/`SelectProfile` — никакой второй фабрики репозиториев
(ADR-8.4). Логирует `admin_profile_created` (ADR-8.10) — без полного
текста `system_instruction`, только `profile_id`/`name`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import CreateProfileCommand
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.shared.logging import get_logger, log_audit_event

_logger = get_logger(__name__)


class CreateProfile:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: CreateProfileCommand) -> UserProfile:
        async with self._repositories() as repositories:
            now = datetime.now(UTC)
            profile = UserProfile(
                id=uuid4(),
                name=command.name,
                description=command.description,
                system_instruction=command.system_instruction,
                response_style=command.response_style,
                target_audience=command.target_audience,
                formality_level=command.formality_level,
                preferred_structure=command.preferred_structure,
                forbidden_phrasing=command.forbidden_phrasing,
                preferred_model=command.preferred_model,
                response_length_hint=command.response_length_hint,
                additional_constraints=command.additional_constraints,
                status=ProfileStatus.ACTIVE,
                is_system=False,
                is_default=False,
                created_at=now,
                updated_at=now,
            )
            saved = await repositories.profiles.create(profile)
            log_audit_event(_logger, "admin_profile_created", profile_id=str(saved.id), name=saved.name)
            return saved
