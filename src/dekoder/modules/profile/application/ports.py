"""
ProfileRepositoryPort (docs/02, §7).

Профиль в MVP только читается во время работы приложения — запись
происходит один раз при старте (см. use_cases.seed_profile): docs/01, §4.3
— «редактирование профиля... в MVP не предусмотрено».
"""

from __future__ import annotations

from typing import Protocol

from dekoder.modules.profile.domain.profile import Profile


class ProfileRepositoryPort(Protocol):
    """Хранит и предоставляет единственный профиль автора."""

    def get_profile(self) -> Profile | None:
        """Возвращает профиль, либо None, если он ещё не загружен (см. seed_profile)."""
        ...

    def save_profile(self, profile: Profile) -> None:
        """Используется только при первичной загрузке (seed), не как редактирование через интерфейс."""
        ...
