"""
`DeactivateProfile` — архивирует профиль (Sprint 8, задача S8-07,
ADR-8.7/8.8).

Единственное место, проверяющее инвариант `is_default` перед
архивированием: профиль с `is_default=True` архивировать запрещено,
иначе `SQLAlchemyProfileRepository.get_active_profile()` (не тронутый в
Sprint 8) сломается для всех пользователей без явного выбора (ADR-8.7,
«Недостатки»). Нарушение — `ApplicationError(code=
"PROFILE_ARCHIVE_DEFAULT_FORBIDDEN")`, которая
`presentation/api/error_handlers.py` маппит на HTTP 409 (ADR-8.8/8.12),
не 400 — это конфликт с текущим состоянием ресурса, не ошибка валидации
входных данных.

`repositories.profiles.archive()` уже идемпотентна на уровне порта
(повторный вызов на уже `ARCHIVED`-профиле не поднимает исключение,
S8-06) — здесь эта идемпотентность не теряется.

Логирует `admin_profile_archived` (ADR-8.10) только при успехе.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import DeactivateProfileCommand, DeactivateProfileResult, DeactivateProfileStatus
from dekoder.shared.errors import ApplicationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class DeactivateProfile:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: DeactivateProfileCommand) -> DeactivateProfileResult:
        async with self._repositories() as repositories:
            existing = await repositories.profiles.get_by_id(command.profile_id)
            if existing is None:
                return DeactivateProfileResult(status=DeactivateProfileStatus.UNKNOWN_PROFILE, profile=None)

            if existing.is_default:
                raise ApplicationError(
                    message=f"Профиль {existing.id} помечен is_default, архивирование запрещено",
                    user_message="Нельзя архивировать профиль по умолчанию.",
                    code="PROFILE_ARCHIVE_DEFAULT_FORBIDDEN",
                )

            archived = await repositories.profiles.archive(command.profile_id)
            _logger.info("admin_profile_archived", profile_id=str(command.profile_id))
            return DeactivateProfileResult(status=DeactivateProfileStatus.ARCHIVED, profile=archived)
