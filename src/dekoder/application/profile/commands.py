"""Команды Author Profile Service (docs/versions/05, §4)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.profile.profile import ProfileSettings
from dekoder.shared.domain.identifiers import ProfileId, UserId


@dataclass(frozen=True)
class CreateAuthorProfileCommand:
    user_id: UserId
    title: str
    settings: ProfileSettings


@dataclass(frozen=True)
class UpdateAuthorProfileCommand:
    user_id: UserId
    profile_id: ProfileId
    title: str | None
    settings: ProfileSettings | None


@dataclass(frozen=True)
class ArchiveAuthorProfileCommand:
    user_id: UserId
    profile_id: ProfileId


@dataclass(frozen=True)
class SetDefaultProfileCommand:
    user_id: UserId
    profile_id: ProfileId
