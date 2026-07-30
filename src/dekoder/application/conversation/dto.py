"""
DTO прикладного слоя первого вертикального среза — вход/выход одного
use case обработки пользовательского сообщения и вызова LLM-провайдера.

Обычные `dataclass`, без Pydantic и без привязки к API-фреймворку
(FastAPI/Telegram/OpenRouter) — это внутренний контракт application-слоя,
не HTTP-модель и не тело запроса конкретного провайдера.

`message_text`/`model_id`/`provider_id` используют доменные value objects
из `domain/conversation/value_objects.py`, где значение — это ввод
пользователя или устойчивый идентификатор. Свободный текст без такой
семантики (системный промпт, текст ответа модели — может быть длиннее
MessageText.MAX_LENGTH, рассчитанного на ввод пользователя) остаётся
обычной `str`.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.conversation.value_objects import MessageText, ModelId, ProviderId
from dekoder.shared.domain.identifiers import CorrelationId


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ProcessUserMessageCommand:
    external_user_id: str
    message_text: MessageText
    correlation_id: CorrelationId
    model_id: ModelId | None = None


@dataclass(frozen=True)
class ProcessUserMessageResult:
    response_text: str
    provider_id: ProviderId
    model_id: ModelId
    duration_ms: float
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_message: MessageText
    model_id: ModelId
    temperature: float
    max_tokens: int
    correlation_id: CorrelationId


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider_id: ProviderId
    model_id: ModelId
    input_tokens: int
    output_tokens: int
    duration_ms: float
