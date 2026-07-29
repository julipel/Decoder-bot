"""ModelCatalogRepository — чтение каталога моделей; без записи в runtime (docs/versions/05, §7)."""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.model_catalog.model_definition import ModelDefinition
from dekoder.shared.domain.identifiers import ModelId, SkillId
from dekoder.shared.domain.value_objects import GenerationType


class ModelCatalogRepository(Protocol):
    def get(self, model_id: ModelId) -> ModelDefinition | None: ...

    def list_all(self) -> list[ModelDefinition]: ...

    def list_compatible(self, skill_id: SkillId, generation_type: GenerationType) -> list[ModelDefinition]: ...
