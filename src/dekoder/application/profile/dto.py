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
