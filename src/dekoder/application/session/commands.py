"""Команды Session Manager (docs/versions/05, §4)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import ModelId, SessionId, SkillId, UserId
from dekoder.shared.domain.value_objects import ContentType


@dataclass(frozen=True)
class StartGenerationSessionCommand:
    user_id: UserId


@dataclass(frozen=True)
class SelectContentTypeCommand:
    session_id: SessionId
    content_type: ContentType


@dataclass(frozen=True)
class SelectSkillCommand:
    session_id: SessionId
    skill_id: SkillId


@dataclass(frozen=True)
class SelectModelCommand:
    """`model_id=None` означает выбор режима «Автоматически» (docs/versions/05, §4)."""

    session_id: SessionId
    model_id: ModelId | None


@dataclass(frozen=True)
class SubmitUserInputCommand:
    session_id: SessionId
    user_input: dict[str, str]


@dataclass(frozen=True)
class CancelSessionCommand:
    session_id: SessionId


@dataclass(frozen=True)
class ResetSessionCommand:
    session_id: SessionId
