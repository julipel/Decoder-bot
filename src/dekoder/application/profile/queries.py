"""Запросы и View DTO Author Profile Service (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.profile.profile import ProfileStatus
from dekoder.shared.domain.identifiers import ProfileId, UserId


@dataclass(frozen=True)
class GetAuthorProfilesQuery:
    user_id: UserId


@dataclass(frozen=True)
class GetAuthorProfileQuery:
    user_id: UserId
    profile_id: ProfileId


@dataclass(frozen=True)
class AuthorProfileView:
    profile_id: ProfileId
    title: str
    status: ProfileStatus
    is_default: bool
