"""Запрос и View DTO Content Skill Service (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import SkillId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


@dataclass(frozen=True)
class GetAvailableSkillsQuery:
    content_type: ContentType | None
    generation_type: GenerationType


@dataclass(frozen=True)
class SkillOptionView:
    skill_id: SkillId
    title: str
    generation_type: GenerationType
    required_input_fields: tuple[str, ...]
