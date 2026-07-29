from __future__ import annotations

from dekoder.application.profile.commands import CreateAuthorProfileCommand
from dekoder.application.profile.ports import ProfileRepository
from dekoder.application.profile.queries import AuthorProfileView


class CreateAuthorProfileUseCase:
    """Проверяет лимит активных профилей (ProfileLimitExceeded) перед созданием (04, §8)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, command: CreateAuthorProfileCommand) -> AuthorProfileView:
        raise NotImplementedError
