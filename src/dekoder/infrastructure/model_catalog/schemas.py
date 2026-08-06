"""
Схема внешнего JSON-контракта файлового каталога моделей
(`infrastructure/model_catalog/catalog.json`, Sprint 7, задача S7-03,
ADR-7.4).

Живёт только в `infrastructure/` — это wire-формат конкретного файла,
application/domain-слои его никогда не видят (возвращается уже
типизированный `domain.model_catalog.entities.AIModel`, не эта модель и
не сырой JSON) — по стилю `infrastructure/llm/schemas.py`.
"""

from __future__ import annotations

from pydantic import BaseModel


class GenerationSettingsSchema(BaseModel):
    temperature: float
    max_tokens: int


class AIModelSchema(BaseModel):
    model_id: str
    display_name: str
    provider: str
    context_window: int
    capabilities: list[str]
    price_tier: str
    availability: str
    recommended_for: list[str]
    default_generation_settings: GenerationSettingsSchema
