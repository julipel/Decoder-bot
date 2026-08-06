"""
`OpenAiEmbeddingProvider` — реализация `EmbeddingProvider` поверх OpenAI
Embeddings API (`POST /embeddings`, Sprint 6, задача S6-05, ADR-6.3).

Стиль — как `OpenRouterLLMAdapter`: `httpx.AsyncClient` внедряется через
конструктор и переиспользуется, адаптер не знает базовый URL (настройка
клиента, bootstrap-слой) и не создаёт клиент сам. Не связан с
`OpenRouterLLMAdapter`/`OpenRouterSettings` — независимый провайдер
(ADR-6.3): OpenRouter не отдаёт embeddings API.

`data[].index` в ответе OpenAI гарантированно соответствует порядку
`input` — тем не менее сортируется явно перед сборкой результата
(документированное поведение API, но не контракт, на который стоит
полагаться слепо для батч-запроса, определяющего порядок фрагментов
одного документа).
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import ValidationError as PydanticValidationError

from dekoder.application.knowledge.ports import EmbeddingProvider
from dekoder.infrastructure.embeddings.schemas import OpenAiEmbeddingRequest, OpenAiEmbeddingResponse
from dekoder.shared.errors import EmbeddingProviderError

_EMBEDDINGS_PATH = "/embeddings"


class OpenAiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = OpenAiEmbeddingRequest(model=self._model, input=list(texts))
        response = await self._post(payload)
        self._raise_for_status(response)
        parsed = self._parse_response(response)

        if len(parsed.data) != len(texts):
            raise EmbeddingProviderError(
                message=f"OpenAI returned {len(parsed.data)} embeddings for {len(texts)} input texts",
                user_message="Не удалось построить эмбеддинги для документа.",
                code="EMBEDDING_PROVIDER_COUNT_MISMATCH",
            )
        return [item.embedding for item in sorted(parsed.data, key=lambda item: item.index)]

    async def _post(self, payload: OpenAiEmbeddingRequest) -> httpx.Response:
        try:
            return await self._client.post(
                _EMBEDDINGS_PATH,
                json=payload.model_dump(),
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.TimeoutException as error:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings request timed out: {error!r}",
                user_message="Сервис эмбеддингов не ответил вовремя, попробуйте ещё раз.",
                code="EMBEDDING_PROVIDER_TIMEOUT",
                cause=error,
            ) from error
        except httpx.HTTPError as error:
            raise EmbeddingProviderError(
                message=f"Network error calling OpenAI embeddings: {error!r}",
                user_message="Не удалось связаться с сервисом эмбеддингов, попробуйте позже.",
                code="EMBEDDING_PROVIDER_NETWORK_ERROR",
                cause=error,
            ) from error

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status == 401:
            raise EmbeddingProviderError(
                message=f"OpenAI rejected the embeddings request as unauthorized (HTTP {status})",
                user_message="Сервис эмбеддингов недоступен из-за ошибки авторизации.",
                code="EMBEDDING_PROVIDER_UNAUTHORIZED",
            )
        if status == 429:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings rate limit exceeded (HTTP {status})",
                user_message="Слишком много запросов к сервису эмбеддингов, попробуйте немного позже.",
                code="EMBEDDING_PROVIDER_RATE_LIMITED",
            )
        if status >= 500:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings server error (HTTP {status})",
                user_message="Сервис эмбеддингов временно недоступен, попробуйте позже.",
                code="EMBEDDING_PROVIDER_SERVER_ERROR",
            )
        if status >= 400:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings returned an unexpected client error (HTTP {status})",
                user_message="Не удалось построить эмбеддинги для документа.",
                code="EMBEDDING_PROVIDER_CLIENT_ERROR",
            )

    def _parse_response(self, response: httpx.Response) -> OpenAiEmbeddingResponse:
        try:
            raw = response.json()
        except ValueError as error:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings returned malformed JSON: {error!r}",
                user_message="Получен некорректный ответ от сервиса эмбеддингов.",
                code="EMBEDDING_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error

        try:
            return OpenAiEmbeddingResponse.model_validate(raw)
        except PydanticValidationError as error:
            raise EmbeddingProviderError(
                message=f"OpenAI embeddings response failed schema validation: {error!r}",
                user_message="Получен некорректный ответ от сервиса эмбеддингов.",
                code="EMBEDDING_PROVIDER_MALFORMED_RESPONSE",
                cause=error,
            ) from error
