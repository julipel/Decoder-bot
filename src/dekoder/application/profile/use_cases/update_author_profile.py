from __future__ import annotations

from dekoder.application.profile.commands import UpdateAuthorProfileCommand
from dekoder.application.profile.ports import ProfileRepository
from dekoder.application.profile.queries import AuthorProfileView


class UpdateAuthorProfileUseCase:
    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, command: UpdateAuthorProfileCommand) -> AuthorProfileView:
        raise NotImplementedError
