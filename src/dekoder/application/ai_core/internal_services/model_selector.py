"""Внутренний коллаборатор ai_core — режим «Автоматически» = первая совместимая модель (docs/versions/05, §9)."""

from __future__ import annotations

from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.domain.model_catalog.model_definition import ModelDefinition
from dekoder.shared.domain.identifiers import ModelId, SkillId
from dekoder.shared.domain.value_objects import GenerationType


class ModelSelector:
    """Может завершиться ModelUnavailable/ModelIncompatible (05, §12)."""

    def __init__(self, model_catalog_repository: ModelCatalogRepository) -> None:
        self._model_catalog_repository = model_catalog_repository

    def select(self, model_id: ModelId | None, skill_id: SkillId, generation_type: GenerationType) -> ModelDefinition:
        raise NotImplementedError
