"""AuthorProfile — стиль, тон, ниша и ограничения контента одного пользователя (docs/versions/04, §4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dekoder.shared.domain.identifiers import ProfileId, UserId


class ProfileStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class ProfileSettings:
    """Value Object — целиком в собственности AuthorProfile, не адресуется отдельно (04, §6)."""

    tone: str
    style: str
    niche: str
    audience: str
    positioning: str
    preferred_vocabulary: tuple[str, ...] = field(default_factory=tuple)
    forbidden_vocabulary: tuple[str, ...] = field(default_factory=tuple)
    preferred_techniques: tuple[str, ...] = field(default_factory=tuple)
    forbidden_techniques: tuple[str, ...] = field(default_factory=tuple)
    formatting_rules: str = ""
    example_texts: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class AuthorProfile:
    profile_id: ProfileId
    user_id: UserId
    title: str
    settings: ProfileSettings
    created_at: datetime
    status: ProfileStatus = ProfileStatus.CREATED
    is_default: bool = False
