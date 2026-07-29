from __future__ import annotations

from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.model_catalog.queries import GetAvailableModelsQuery, ModelOptionView


class GetAvailableModelsUseCase:
    def __init__(self, model_catalog_repository: ModelCatalogRepository) -> None:
        self._model_catalog_repository = model_catalog_repository

    def execute(self, query: GetAvailableModelsQuery) -> list[ModelOptionView]:
        raise NotImplementedError
