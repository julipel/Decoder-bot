"""
Схемы внешнего JSON-контракта OpenAI Chat Completions API (или
совместимого с ним агрегатора, настраиваемого через `LLM_PROVIDER_*`).

Живут только в `infrastructure/` — это wire-формат конкретного
провайдера, application-слой его никогда не видит (возвращается уже
типизированный `LLMResponse`, не эти модели и не сырой JSON).
Pydantic здесь уместен: инфраструктура вправе зависеть от внешних
библиотек, а валидация формы ответа — ровно то, что нужно, чтобы отличить
`LLM_PROVIDER_MALFORMED_RESPONSE` от прочих ошибок.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatCompletionRequestMessage(BaseModel):
    role: str
    content: str


class ChatCompletionPlugin(BaseModel):
    """
    Провайдер-специфичное расширение Chat Completions API (OpenRouter-
    совместимый `plugins`-параметр, поддержан RouterAI, ADR: внеспринтовая
    задача 2026-09-09) — единственное применение сейчас: `{"id": "web"}`
    включает веб-поиск как middleware поверх любой модели агрегатора.
    Живёт только в `infrastructure/` (docstring модуля) — application не
    знает об этом формате, только о `LLMRequest.web_search: bool`.
    """

    id: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatCompletionRequestMessage]
    temperature: float
    max_tokens: int
    plugins: list[ChatCompletionPlugin] | None = None


class ChatCompletionResponseMessage(BaseModel):
    role: str
    content: str


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatCompletionResponseMessage
    finish_reason: str | None = None


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int | None = None


class ChatCompletionResponse(BaseModel):
    id: str | None = None
    model: str | None = None
    choices: list[ChatCompletionChoice] = Field(default_factory=list)
    usage: ChatCompletionUsage | None = None
