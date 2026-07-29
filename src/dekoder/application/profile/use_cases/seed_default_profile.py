from __future__ import annotations

from dekoder.application.profile.ports import ProfileRepository


class SeedDefaultProfileUseCase:
    """Первичная загрузка seed-профиля при пустом хранилище (docs/versions/06, §6)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, seed_path: str) -> None:
        raise NotImplementedError
