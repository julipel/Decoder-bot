"""
DTO прикладного слоя — вход/выход use case обработки пользовательского
сообщения и вызова LLM-провайдера.

Обычные `dataclass`, без Pydantic и без привязки к API-фреймворку
(FastAPI/Telegram/OpenRouter) — это внутренний контракт application-слоя,
не HTTP-модель и не тело запроса конкретного провайдера.

`model_id`/`provider_id` используют доменные value objects из
`domain/conversation/value_objects.py` — устойчивые идентификаторы.
Свободный текст без такой семантики (системный промпт, текст ответа
модели — может быть длиннее MessageText.MAX_LENGTH, рассчитанного на
ввод пользователя) остаётся обычной `str`.

`ProcessUserMessageCommand.message_text` — намеренно `str`, а не
`MessageText`: это сырой текст, пришедший из driving-адаптера (Telegram
и т. п.), ещё не проверенный. Проверка — ответственность
`ProcessUserMessage.execute()` (доменный `MessageText`, требование
«для проверки текста используй доменный MessageText»), а не самого DTO —
иначе невалидный ввод падал бы при создании команды, а не как
наблюдаемый исход выполнения use case'а.

`ProcessUserMessageCommand.telegram_user_id` (Sprint 2, задача S2-06,
было `external_user_id: str`) — переименован и типизирован как `int`,
чтобы совпадать буквально с сигнатурой `UserRepository.
get_or_create_by_telegram_user_id(telegram_user_id: int)`
(`application/user/ports.py`): единственный источник этого значения —
`Update.effective_user.id` (Telegram SDK, всегда `int`), промежуточное
преобразование в `str` было артефактом Sprint 1 (ещё не было ни одного
репозитория) и никакой сохранившейся причины для него не осталось.

`LLMMessage`/`LLMRequest.messages` (Sprint 2, задача S2-06) заменяют
`LLMRequest.user_message: MessageText` — порт `LLMProvider` теперь несёт
всю историю активного диалога (система формирует контекст из
`MessageRepository.history()`, backlog_2.md §11), а не одно сообщение.
`LLMMessage` — минимальная роль+текст, без какой-либо специфики
конкретного SDK (OpenAI/OpenRouter/Anthropic/...): её вводит и
преобразует во внешний формат исключительно `infrastructure/llm/`
(`OpenRouterLLMAdapter`). `role` — обычная `str` (не доменный
`MessageRole`): `LLMRequest` — контракт LLM-порта, а не диалоговый
агрегат, и не должен быть жёстко привязан к `domain/conversation/
entities.py`; преобразование `MessageRole.USER/ASSISTANT -> "user"/
"assistant"` выполняет вызывающий Use Case (значения enum и так
совпадают со строками ролей, см. `domain/conversation/entities.py`).

`StartNewConversationCommand`/`StartNewConversationResult` (Sprint 2,
задача S2-07) — вход/выход use case `StartNewConversation`
(`application/conversation/use_cases/start_new_conversation.py`), тот же
стиль, что и `ProcessUserMessageCommand`/`ProcessUserMessageResult`.
`StartNewConversationCommand` содержит только `telegram_user_id` — в
отличие от `ProcessUserMessageCommand`, тут нет ни текста сообщения, ни
`correlation_id`/`model_id`: use case не логирует и не вызывает LLM
(команда /new к Telegram Adapter в этой задаче ещё не подключается —
S2-08). `StartNewConversationResult.conversation_id: UUID | None` — `None`
означает «пользователь не найден» (в отличие от `ProcessUserMessage`,
`StartNewConversation` не создаёт пользователя автоматически,
backlog_2_tasks.md S2-07) и не является ошибкой: результат в этом случае
всё равно считается успешным.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.shared.domain.identifiers import CorrelationId


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ProcessUserMessageCommand:
    telegram_user_id: int
    message_text: str
    correlation_id: CorrelationId
    model_id: ModelId | None = None


@dataclass(frozen=True)
class ProcessUserMessageResult:
    response_text: str
    provider_id: ProviderId
    model_id: ModelId
    duration_ms: float
    conversation_id: UUID
    message_id: UUID
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class LLMMessage:
    """Одно сообщение истории диалога в форме, которую видит LLM-порт — роль + текст, без специфики SDK."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    messages: Sequence[LLMMessage]
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


@dataclass(frozen=True)
class StartNewConversationCommand:
    telegram_user_id: int


@dataclass(frozen=True)
class StartNewConversationResult:
    conversation_id: UUID | None
