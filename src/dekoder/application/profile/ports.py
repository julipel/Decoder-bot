"""ProfileRepository — хранение AuthorProfile (docs/versions/02, §8; docs/versions/05, §7)."""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.profile.profile import AuthorProfile
from dekoder.shared.domain.identifiers import ProfileId, UserId


class ProfileRepository(Protocol):
    def add(self, profile: AuthorProfile) -> None: ...

    def get(self, profile_id: ProfileId) -> AuthorProfile | None: ...

    def list_for_user(self, user_id: UserId) -> list[AuthorProfile]: ...

    def update(self, profile: AuthorProfile) -> None: ...

    def archive(self, profile_id: ProfileId) -> None: ...
