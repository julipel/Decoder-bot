from __future__ import annotations

from dekoder.application.profile.commands import SetDefaultProfileCommand
from dekoder.application.profile.ports import ProfileRepository


class SetDefaultProfileUseCase:
    """Гарантирует не более одного профиля с флагом is_default одновременно (04, §8)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, command: SetDefaultProfileCommand) -> None:
        raise NotImplementedError
