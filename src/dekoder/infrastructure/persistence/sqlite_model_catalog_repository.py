from __future__ import annotations

from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.domain.model_catalog.model_definition import ModelDefinition
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import ModelId, SkillId
from dekoder.shared.domain.value_objects import GenerationType


class SqliteModelCatalogRepository(ModelCatalogRepository):
    """Read-only: каталог моделей — только seed/конфигурация (docs/versions/02, §6)."""

    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get(self, model_id: ModelId) -> ModelDefinition | None:
        raise NotImplementedError

    def list_all(self) -> list[ModelDefinition]:
        raise NotImplementedError

    def list_compatible(self, skill_id: SkillId, generation_type: GenerationType) -> list[ModelDefinition]:
        raise NotImplementedError
