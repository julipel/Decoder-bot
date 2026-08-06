"""
`GenerationSettings` (Sprint 7, задача S7-02, ADR-7.3) — параметры генерации
по умолчанию для конкретной модели каталога.

Единственное поле каталога `AIModel`, реально влияющее на поведение
генерации (не информационное, в отличие от `context_window`/`capabilities`/
`price_tier`/`recommended_for`) — `ProcessUserMessage` берёт
`temperature`/`max_tokens` отсюда при построении `LLMRequest` (ADR-7.7).

Ноль зависимостей от SQLAlchemy/Telegram/FastAPI/JSON — чистый Python, как
`domain/memory/value_objects.py`. Ошибки — обычный `ValueError`, отдельная
доменная ошибка не оправдана (claude.md §20, по прецеденту `UserProfile`/
`MemoryRecord`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    """Параметры генерации по умолчанию для модели каталога — `temperature`/`max_tokens`."""

    temperature: float
    max_tokens: int

    def __post_init__(self) -> None:
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature должна быть в диапазоне [0.0, 2.0]")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens должен быть положительным")
