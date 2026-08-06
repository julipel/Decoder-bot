"""
`ConfigModelCatalogRepository` — файловая реализация `ModelCatalogRepository`
(Sprint 7, задача S7-03, ADR-7.4).

Читает и парсит JSON-файл (по умолчанию — `infrastructure/model_catalog/
catalog.json`) в список `AIModel` — ОДИН РАЗ при построении репозитория
(`__init__`), не на каждый вызов (по прецеденту `FileTemplateRepository`,
Sprint 4, ADR-4.2). Никакого обращения к БД/Alembic/HTTP — только чтение
файла, никакой записи/кэширования на диск.

Путь к файлу — `ModelCatalogSettings.catalog_path` (`shared/config.py`),
не хардкод-строка (ADR-7.4).

Ошибка при отсутствующем/повреждённом файле или невалидной записи —
`shared.errors.InfrastructureError` (fail-fast при построении, не при
первом вызове `get`/`list_all`) — по прецеденту `FileTemplateRepository`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel
from dekoder.domain.model_catalog.enums import (
    AIProvider,
    ModelAvailability,
    ModelCapability,
    ModelPriceTier,
)
from dekoder.domain.model_catalog.value_objects import GenerationSettings
from dekoder.infrastructure.model_catalog.schemas import AIModelSchema
from dekoder.shared.errors import InfrastructureError

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "catalog.json"
"""Путь к сид-каталогу по умолчанию — рядом с этим модулем (`infrastructure/model_catalog/catalog.json`)."""


class ConfigModelCatalogRepository:
    """
    Реализация `ModelCatalogRepository` (`application/model_catalog/
    ports.py`) поверх статичного JSON-файла — структурное соответствие
    протоколу (`@runtime_checkable`), без явного наследования, по стилю
    `FileTemplateRepository`.

    `get()`/`list_all()` — синхронные, без I/O: вся файловая работа
    выполнена в `__init__`, результат закэширован в `dict[ModelId, AIModel]`.
    """

    def __init__(self, catalog_path: Path | None = None) -> None:
        path = catalog_path if catalog_path is not None else DEFAULT_CATALOG_PATH
        self._models: dict[ModelId, AIModel] = self._load(path)

    def get(self, model_id: ModelId) -> AIModel | None:
        return self._models.get(model_id)

    def list_all(self) -> Sequence[AIModel]:
        return list(self._models.values())

    @staticmethod
    def _load(path: Path) -> dict[ModelId, AIModel]:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as error:
            raise InfrastructureError(
                message=f"Не удалось прочитать файл каталога моделей: {path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as error:
            raise InfrastructureError(
                message=f"Каталог моделей повреждён (невалидный JSON): {path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        models: dict[ModelId, AIModel] = {}
        for entry in entries:
            model = ConfigModelCatalogRepository._build_model(path, entry)
            models[model.model_id] = model
        return models

    @staticmethod
    def _build_model(path: Path, entry: object) -> AIModel:
        try:
            schema = AIModelSchema.model_validate(entry)
        except PydanticValidationError as error:
            raise InfrastructureError(
                message=f"Каталог моделей содержит невалидную запись: {path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        try:
            return AIModel(
                model_id=ModelId(schema.model_id),
                display_name=schema.display_name,
                provider=AIProvider(schema.provider),
                context_window=schema.context_window,
                capabilities=frozenset(ModelCapability(value) for value in schema.capabilities),
                price_tier=ModelPriceTier(schema.price_tier),
                availability=ModelAvailability(schema.availability),
                recommended_for=tuple(schema.recommended_for),
                default_generation_settings=GenerationSettings(
                    temperature=schema.default_generation_settings.temperature,
                    max_tokens=schema.default_generation_settings.max_tokens,
                ),
            )
        except ValueError as error:
            raise InfrastructureError(
                message=f"Каталог моделей содержит невалидную запись ({schema.model_id}): {path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error
