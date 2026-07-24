"""
LLMPort (docs/02, §7 и §16.2).

LLMRequestContext — собственный DTO модуля llm, а НЕ тип из ai_core.
Так LLM Adapter не зависит от домена AI Core, а AI Core сам конвертирует
свой ConversationContext в этот DTO перед вызовом порта — иначе возник бы
цикл ai_core → llm → ai_core (см. docs/03, риски циклических импортов).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LLMRequestContext:
    """Плоское представление единого контекста запроса, без знания о ai_core."""

    system_instructions: str
    context_sections: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMPort(Protocol):
    """Генерирует ответ активного поставщика (docs/01, §4.2: LLM_PROVIDER/LLM_MODEL)."""

    def complete(self, context: LLMRequestContext) -> LLMResponse: ...
