from __future__ import annotations

from dekoder.application.profile.ports import ProfileRepository
from dekoder.application.profile.queries import AuthorProfileView, GetAuthorProfileQuery


class GetAuthorProfileUseCase:
    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, query: GetAuthorProfileQuery) -> AuthorProfileView | None:
        raise NotImplementedError
