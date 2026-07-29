from __future__ import annotations

from dekoder.application.profile.commands import ArchiveAuthorProfileCommand
from dekoder.application.profile.ports import ProfileRepository


class ArchiveAuthorProfileUseCase:
    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, command: ArchiveAuthorProfileCommand) -> None:
        raise NotImplementedError
