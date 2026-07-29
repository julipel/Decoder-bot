"""Запрос и View DTO Session Manager (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.session.session import SessionStep
from dekoder.shared.domain.identifiers import ModelId, SessionId, SkillId
from dekoder.shared.domain.value_objects import ContentType


@dataclass(frozen=True)
class GetSessionQuery:
    session_id: SessionId


@dataclass(frozen=True)
class GenerationSessionView:
    session_id: SessionId
    current_step: SessionStep
    content_type: ContentType | None
    selected_skill_id: SkillId | None
    selected_model_id: ModelId | None
