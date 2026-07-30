"""
Схемы внешнего JSON-контракта OpenRouter Chat Completions API.

Живут только в `infrastructure/` — это wire-формат конкретного
провайдера, application-слой его никогда не видит (возвращается уже
типизированный `LLMResponse`, не эти модели и не сырой JSON).
Pydantic здесь уместен: инфраструктура вправе зависеть от внешних
библиотек, а валидация формы ответа — ровно то, что нужно, чтобы отличить
`LLM_PROVIDER_MALFORMED_RESPONSE` от прочих ошибок.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OpenRouterChatMessage(BaseModel):
    role: str
    content: str


class OpenRouterChatCompletionRequest(BaseModel):
    model: str
    messages: list[OpenRouterChatMessage]
    temperature: float
    max_tokens: int


class OpenRouterResponseMessage(BaseModel):
    role: str
    content: str


class OpenRouterChoice(BaseModel):
    index: int
    message: OpenRouterResponseMessage
    finish_reason: str | None = None


class OpenRouterUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int | None = None


class OpenRouterChatCompletionResponse(BaseModel):
    id: str | None = None
    model: str | None = None
    choices: list[OpenRouterChoice] = Field(default_factory=list)
    usage: OpenRouterUsage | None = None
