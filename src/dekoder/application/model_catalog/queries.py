"""Запрос и View DTO Model Catalog (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.model_catalog.model_definition import ModelAvailabilityStatus
from dekoder.shared.domain.identifiers import ModelId, SkillId
from dekoder.shared.domain.value_objects import GenerationType


@dataclass(frozen=True)
class GetAvailableModelsQuery:
    skill_id: SkillId
    generation_type: GenerationType


@dataclass(frozen=True)
class ModelOptionView:
    model_id: ModelId
    display_name: str
    provider: str
    availability_status: ModelAvailabilityStatus
