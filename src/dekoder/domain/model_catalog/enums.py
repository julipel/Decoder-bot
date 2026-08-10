"""
Enum'ы доменной модели каталога AI-моделей (Sprint 7, задача S7-02,
ADR-7.3) — Этап 9 «Плана реализации.md» (выбор AI-модели пользователем).

Конкретные значения — явная MVP-интерпретация §15.2/§15.3 «Плана
реализации.md» (документ называет сущности этапа, но не задаёт конкретных
значений enum'ов), по прецеденту ADR-3.1/ADR-5.3.

`Enum`, не `str, Enum` — по стилю `domain/profile/value_objects.py::
ProfileStatus`/`domain/memory/value_objects.py`.
"""

from __future__ import annotations

from enum import Enum


class AIProvider(Enum):
    """
    Семейство поставщика модели — минимальный набор, покрывающий основные
    семейства моделей выбранного агрегатора (ADR-7.3).
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    YANDEX = "yandex"
    META = "meta"
    OTHER = "other"


class ModelCapability(Enum):
    """
    Возможность модели — минимальный набор, достаточный для отображения в
    `/model` (ADR-7.3); расширяется по мере реальной эксплуатации (YAGNI).
    """

    TEXT = "text"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"


class ModelAvailability(Enum):
    """
    Доступность модели — статичное поле каталога (не результат живой
    проверки health-check поставщика в MVP, ADR-7.3).
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ModelPriceTier(Enum):
    """Ценовая категория модели — информационное поле каталога (ADR-7.3), не участвует в логике выбора/отказа."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
