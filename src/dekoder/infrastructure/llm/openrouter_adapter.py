"""
OpenRouterLLMAdapter — реализация LLMProvider поверх OpenRouter Chat
Completions API (`POST /chat/completions`, OpenAI-совместимый формат).

Не выбирает модель, не решает бизнес-вопросов — только переводит
`LLMRequest` во внешний HTTP-запрос и внешний ответ обратно в
`LLMResponse` (docs-инвариант: адаптер не принимает решений, которые
должны приниматься выше). `httpx.AsyncClient` передаётся через
конструктор и переиспользуется — адаптер не знает базовый URL OpenRouter
(это настройка клиента, конфигурируется в bootstrap-слое) и не создаёт
клиент сам.

Sprint 2 (задача S2-06): `LLMRequest.messages` несёт всю историю
активного диалога (`LLMMessage(role, content)`, роль уже "user"/
"assistant" — строковая, не доменный `MessageRole`), не одно сообщение
(`user_message: MessageText` из Sprint 1 удалён). Адаптер строит
`messages=[system, *history]` — переводит `LLMMessage` в
`OpenRouterChatMessage` один в один (`role`/`content`), никакой
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
    OpenRouterChatCompletionRequest,
    OpenRouterChatCompletionResponse,
    OpenRouterChatMessage,
)
from dekoder.shared.errors import LLMProviderError

_CHAT_COMPLETIONS_PATH = "/chat/completions"
_PROVIDER_ID = ProviderId("openrouter")


class OpenRouterLLMAdapter(LLMProvider):
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        http_referer: str | None = None,
        x_title: str | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._http_referer = http_referer
        self._x_title = x_title

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = OpenRouterChatCompletionRequest(
            model=request.model_id.value,
            messages=[
                OpenRouterChatMessage(role="system", content=request.system_prompt),
                *(OpenRouterChatMessage(role=message.role, content=message.content) for message in request.messages),
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        started_at = time.monotonic()
        http_response = await self._post(payload)
        duration_ms = (time.monotonic() - started_at) * 1000

        self._raise_for_status(http_response)
        parsed = self._parse_response(http_response)
        return self._to_llm_response(parsed, request.model_id, duration_ms)

    async def _post(self, payload: OpenRouterChatCompletionRequest) -> httpx.Response:
        try:
            return await self._client.post(
                _CHAT_COMPLETIONS_PATH,
                json=payload.model_dump(),
                headers=self._build_headers(),
            )
        except httpx.TimeoutException as error:
            raise LLMProviderError(
                message=f"OpenRouter request timed out: {error!r}",
                user_message="Модель не ответила вовремя, попробуйте ещё раз.",
                code="LLM_PROVIDER_TIMEOUT",
                cause=error,
            ) from error
        except httpx.HTTPError as error:
            # Сетевые сбои (DNS, обрыв соединения и т.п.) — не HTTP-статус,
            # httpx поднимает их до получения какого-либо ответа.
            raise LLMProviderError(
                message=f"Network error calling OpenRouter: {error!r}",
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
                message=f"OpenRouter rejected the request as unauthorized (HTTP {status})",
                user_message="Сервис модели недоступен из-за ошибки авторизации.",
                code="LLM_PROVIDER_UNAUTHORIZED",
            )
        if status == 429:
            raise LLMProviderError(
                message=f"OpenRouter rate limit exceeded (HTTP {status})",
                user_message="Слишком много запросов к модели, попробуйте немного позже.",
                code="LLM_PROVIDER_RATE_LIMITED",
            )
        if status >= 500:
            raise LLMProviderError(
                message=f"OpenRouter server error (HTTP {status})",
                user_message="Сервис модели временно недоступен, попробуйте позже.",
                code="LLM_PROVIDER_SERVER_ERROR",
            )
        if status >= 400:
            raise LLMProviderError(
                message=f"OpenRouter returned an unexpected client error (HTTP {status})",
                user_message="Не удалось получить ответ от модели.",
                code="LLM_PROVIDER_CLIENT_ERROR",
            )

    def _parse_response(self, response: httpx.Response) -> OpenRouterChatCompletionResponse:
        try:
            raw = response.json()
        except ValueError as error:
            raise LLMProviderError(
                message=f"OpenRouter returned malformed JSON: {error!r}",
                user_message="Получен некорректный ответ от модели.",
                code="LLM_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error

        try:
            return OpenRouterChatCompletionResponse.model_validate(raw)
        except PydanticValidationError as error:
            raise LLMProviderError(
                message=f"OpenRouter response failed schema validation: {error!r}",
                user_message="Получен некорректный ответ от модели.",
                code="LLM_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error

    def _to_llm_response(
        self,
        parsed: OpenRouterChatCompletionResponse,
        requested_model: ModelId,
        duration_ms: float,
    ) -> LLMResponse:
        if not parsed.choices:
            raise LLMProviderError(
                message="OpenRouter response contained no choices",
                user_message="Модель не вернула ответ.",
                code="LLM_PROVIDER_EMPTY_CHOICES",
            )

        usage = parsed.usage
        return LLMResponse(
            text=parsed.choices[0].message.content,
            provider_id=_PROVIDER_ID,
            model_id=ModelId(parsed.model) if parsed.model else requested_model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            duration_ms=duration_ms,
        )
