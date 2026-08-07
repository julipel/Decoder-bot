"""
DTO прикладного слоя для профильного выбора (Sprint 3, задача S3-06) —
вход/выход `ListProfiles`/`GetActiveProfile`/`SelectProfile`.

Тот же стиль, что и `application/conversation/dto.py`: обычные
`dataclass(frozen=True)`, без Pydantic и без привязки к Telegram SDK —
внутренний контракт application-слоя.

`GetActiveProfileResult.profile: UserProfile | None` и
`SelectProfileResult` со статусом (не исключением) на ожидаемые
отрицательные исходы — по тому же принципу, что и
`StartNewConversationResult.conversation_id: UUID | None`/
`ClearConversationResult.status` (`application/conversation/dto.py`):
«пользователь ещё не взаимодействовал с ботом» и «неизвестный
profile_id» — штатные исходы, не ошибки.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.entities import UserProfile


@dataclass(frozen=True)
class ListProfilesResult:
    profiles: tuple[UserProfile, ...]


@dataclass(frozen=True)
class GetActiveProfileCommand:
    telegram_user_id: int


@dataclass(frozen=True)
class GetActiveProfileResult:
    """`profile is None` означает, что `telegram_user_id` ещё ни разу не взаимодействовал с ботом."""

    profile: UserProfile | None


@dataclass(frozen=True)
class SelectProfileCommand:
    telegram_user_id: int
    profile_id: UUID


class SelectProfileStatus(Enum):
    """Три исхода `SelectProfile` — по тому же образцу, что и `ClearConversationStatus`."""

    SELECTED = "selected"
    UNKNOWN_USER = "unknown_user"
    UNKNOWN_PROFILE = "unknown_profile"


@dataclass(frozen=True)
class SelectProfileResult:
    """`profile` заполнено только при `status == SelectProfileStatus.SELECTED`."""

    status: SelectProfileStatus
    profile: UserProfile | None


@dataclass(frozen=True)
class CreateProfileCommand:
    """
    Вход `CreateProfile` (Sprint 8, задача S8-07, ADR-8.7/8.8).

    Намеренно НЕ содержит `is_system`/`is_default`/`status` — эти три
    поля не принимаются из административного REST-запроса ни в каком
    виде; `CreateProfile.execute()` всегда создаёт профиль с
    `is_system=False, is_default=False, status=ProfileStatus.ACTIVE`.
    """

    name: str
    description: str
    system_instruction: str
    response_style: str
    target_audience: str
    formality_level: str
    preferred_structure: str
    forbidden_phrasing: tuple[str, ...] = ()
    preferred_model: ModelId | None = None
    response_length_hint: str | None = None
    additional_constraints: str = ""


@dataclass(frozen=True)
class UpdateProfileCommand:
    """
    Вход `UpdateProfile` — частичное обновление (`PATCH`, Sprint 8,
    задача S8-07/S8-08, ADR-8.7/8.8). Все поля, кроме `profile_id`,
    по умолчанию `None`, что означает «не менять» — `changed_fields()`
    возвращает только явно переданные (не-`None`) поля, пригодные для
    `dataclasses.replace(existing, **command.changed_fields(), ...)`.

    Упрощение MVP-уровня (не в скоупе Sprint 8, YAGNI): `None` всегда
    означает «не менять», в т.ч. для `preferred_model`/
    `response_length_hint`, которые в домене допускают `None` как
    содержательное значение — явно ОЧИСТИТЬ их обратно в `None` через
    `PATCH` в этом спринте нельзя, отдельный механизм при необходимости
    — будущая задача.

    Намеренно НЕ содержит `is_system`/`is_default`/`status` — они
    read-only через `PATCH /admin/profiles/{id}`; `status` меняется
    только через отдельный `DeactivateProfile`/`archive`-эндпоинт.
    """

    profile_id: UUID
    name: str | None = None
    description: str | None = None
    system_instruction: str | None = None
    response_style: str | None = None
    target_audience: str | None = None
    formality_level: str | None = None
    preferred_structure: str | None = None
    forbidden_phrasing: tuple[str, ...] | None = None
    preferred_model: ModelId | None = None
    response_length_hint: str | None = None
    additional_constraints: str | None = None

    def changed_fields(self) -> dict[str, object]:
        candidates: dict[str, object] = {
            "name": self.name,
            "description": self.description,
            "system_instruction": self.system_instruction,
            "response_style": self.response_style,
            "target_audience": self.target_audience,
            "formality_level": self.formality_level,
            "preferred_structure": self.preferred_structure,
            "forbidden_phrasing": self.forbidden_phrasing,
            "preferred_model": self.preferred_model,
            "response_length_hint": self.response_length_hint,
            "additional_constraints": self.additional_constraints,
        }
        return {key: value for key, value in candidates.items() if value is not None}


@dataclass(frozen=True)
class DeactivateProfileCommand:
    profile_id: UUID


class DeactivateProfileStatus(Enum):
    """Два исхода `DeactivateProfile` (Sprint 8, S8-07) — запрет `is_default=True` поднимает исключение, не статус."""

    ARCHIVED = "archived"
    UNKNOWN_PROFILE = "unknown_profile"


@dataclass(frozen=True)
class DeactivateProfileResult:
    """`profile` заполнено только при `status == DeactivateProfileStatus.ARCHIVED`."""

    status: DeactivateProfileStatus
    profile: UserProfile | None


@dataclass(frozen=True)
class ListAllProfilesResult:
    """Sprint 8, S8-07 — все профили каталога независимо от `status` (в отличие от `ListProfilesResult`)."""

    profiles: tuple[UserProfile, ...]
