"""
OpenAiCompatibleLLMAdapter — реализация LLMProvider поверх произвольного
OpenAI-Chat-Completions-совместимого API (`POST /chat/completions`).

Не выбирает модель, не решает бизнес-вопросов — только переводит
`LLMRequest` во внешний HTTP-запрос и внешний ответ обратно в
`LLMResponse` (docs-инвариант: адаптер не принимает решений, которые
должны приниматься выше). `httpx.AsyncClient` передаётся через
конструктор и переиспользуется — адаптер не знает базовый URL провайдера
(это настройка клиента, конфигурируется в bootstrap-слое) и не создаёт
клиент сам.

Sprint 11 (задача S11-01, ADR-11.1): адаптер обобщён с прежнего
`OpenRouterLLMAdapter` — конкретный провайдер (OpenRouter или любой иной
OpenAI-Chat-Completions-совместимый агрегатор) больше не хардкодится:
`provider_id: ProviderId` — обязательный конструкторный параметр, не
модульная константа, значение приходит из `LLM_PROVIDER_PROVIDER_ID`.
`http_referer`/`x_title` остаются опциональными параметрами — это не
универсальные заголовки Chat Completions API, а необязательный
OpenRouter-совместимый бонус (`HTTP-Referer`/`X-Title`, атрибуция в
дашборде OpenRouter); для прочих агрегаторов это просто лишние,
безвредные HTTP-заголовки, которые сервер обычно игнорирует.

Sprint 2 (задача S2-06): `LLMRequest.messages` несёт всю историю
активного диалога (`LLMMessage(role, content)`, роль уже "user"/
"assistant" — строковая, не доменный `MessageRole`), не одно сообщение
(`user_message: MessageText` из Sprint 1 удалён). Адаптер строит
`messages=[system, *history]` — переводит `LLMMessage` в
`ChatCompletionRequestMessage` один в один (`role`/`content`), никакой
дополнительной интерпретации истории здесь нет: решение о том, какие
сообщения входят в контекст, принимает `ProcessUserMessage`, не адаптер.
"""

from __future__ import annotations

import time

import httpx
from pydantic import ValidationError as PydanticValidationError

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import LLMProvider
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.llm.schemas import (
    ChatCompletionRequest,
    ChatCompletionRequestMessage,
    ChatCompletionResponse,
)
from dekoder.shared.errors import LLMProviderError
from dekoder.shared.logging import get_logger

_CHAT_COMPLETIONS_PATH = "/chat/completions"

_logger = get_logger(__name__)


class OpenAiCompatibleLLMAdapter(LLMProvider):
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        provider_id: ProviderId,
        http_referer: str | None = None,
        x_title: str | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._provider_id = provider_id
        self._http_referer = http_referer
        self._x_title = x_title

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = ChatCompletionRequest(
            model=request.model_id.value,
            messages=[
                ChatCompletionRequestMessage(role="system", content=request.system_prompt),
                *(
                    ChatCompletionRequestMessage(role=message.role, content=message.content)
                    for message in request.messages
                ),
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        started_at = time.monotonic()
        http_response = await self._post(payload)
        duration_ms = (time.monotonic() - started_at) * 1000

        self._raise_for_status(http_response)
        parsed = self._parse_response(http_response)
        llm_response = self._to_llm_response(parsed, request.model_id, duration_ms)
        _logger.info(
            "llm_generation_completed",
            provider=self._provider_id.value,
            model=request.model_id.value,
            duration_ms=round(duration_ms, 1),
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            correlation_id=request.correlation_id,
        )
        return llm_response

    async def _post(self, payload: ChatCompletionRequest) -> httpx.Response:
        try:
            return await self._client.post(
                _CHAT_COMPLETIONS_PATH,
                json=payload.model_dump(),
                headers=self._build_headers(),
            )
        except httpx.TimeoutException as error:
            raise LLMProviderError(
                message=f"LLM provider request timed out: {error!r}",
                user_message="Модель не ответила вовремя, попробуйте ещё раз.",
                code="LLM_PROVIDER_TIMEOUT",
                cause=error,
            ) from error
        except httpx.HTTPError as error:
            # Сетевые сбои (DNS, обрыв соединения и т.п.) — не HTTP-статус,
            # httpx поднимает их до получения какого-либо ответа.
            raise LLMProviderError(
                message=f"Network error calling LLM provider: {error!r}",
                user_message="Не удалось связаться с сервисом модели, попробуйте позже.",
                code="LLM_PROVIDER_NETWORK_ERROR",
                cause=error,
            ) from error

    def _build_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._x_title:
            headers["X-Title"] = self._x_title
        return headers

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status == 401:
            raise LLMProviderError(
                message=f"LLM provider rejected the request as unauthorized (HTTP {status})",
                user_message="Сервис модели недоступен из-за ошибки авторизации.",
                code="LLM_PROVIDER_UNAUTHORIZED",
            )
        if status == 429:
            raise LLMProviderError(
                message=f"LLM provider rate limit exceeded (HTTP {status})",
                user_message="Слишком много запросов к модели, попробуйте немного позже.",
                code="LLM_PROVIDER_RATE_LIMITED",
            )
        if status >= 500:
            raise LLMProviderError(
                message=f"LLM provider server error (HTTP {status})",
                user_message="Сервис модели временно недоступен, попробуйте позже.",
                code="LLM_PROVIDER_SERVER_ERROR",
            )
        if status >= 400:
            raise LLMProviderError(
                message=f"LLM provider returned an unexpected client error (HTTP {status})",
                user_message="Не удалось получить ответ от модели.",
                code="LLM_PROVIDER_CLIENT_ERROR",
            )

    def _parse_response(self, response: httpx.Response) -> ChatCompletionResponse:
        try:
            raw = response.json()
        except ValueError as error:
            raise LLMProviderError(
                message=f"LLM provider returned malformed JSON: {error!r}",
                user_message="Получен некорректный ответ от модели.",
                code="LLM_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error

        try:
            return ChatCompletionResponse.model_validate(raw)
        except PydanticValidationError as error:
            raise LLMProviderError(
                message=f"LLM provider response failed schema validation: {error!r}",
                user_message="Получен некорректный ответ от модели.",
                code="LLM_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error

    def _to_llm_response(
        self,
        parsed: ChatCompletionResponse,
        requested_model: ModelId,
        duration_ms: float,
    ) -> LLMResponse:
        if not parsed.choices:
            raise LLMProviderError(
                message="LLM provider response contained no choices",
                user_message="Модель не вернула ответ.",
                code="LLM_PROVIDER_EMPTY_CHOICES",
            )

        usage = parsed.usage
        return LLMResponse(
            text=parsed.choices[0].message.content,
            provider_id=self._provider_id,
            model_id=ModelId(parsed.model) if parsed.model else requested_model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            duration_ms=duration_ms,
        )
