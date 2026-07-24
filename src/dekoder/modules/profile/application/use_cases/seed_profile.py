"""
Первичная загрузка профиля при пустой базе (docs/01, §2.3): «профиль...
первоначально загружается из конфигурационного файла или начальных
данных базы». Единственная реальная бизнес-операция сервиса профиля.
"""

from __future__ import annotations

from dekoder.modules.profile.application.ports import ProfileRepositoryPort
from dekoder.modules.profile.domain.profile import Profile


class SeedProfileIfMissingUseCase:
    """Загружает профиль из seed-источника, только если в базе ещё нет записи."""

    def __init__(self, profile_repository: ProfileRepositoryPort) -> None:
        self._profile_repository = profile_repository

    def execute(self, seed_profile: Profile) -> None:
        raise NotImplementedError
