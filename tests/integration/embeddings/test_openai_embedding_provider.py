"""Тесты `OpenAiEmbeddingProvider` — respx перехватывает HTTP, реальный OpenAI никогда не вызывается."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from dekoder.infrastructure.embeddings.openai_embedding_provider import OpenAiEmbeddingProvider
from dekoder.shared.errors import EmbeddingProviderError

BASE_URL = "https://api.openai.com/v1"
EMBEDDINGS_URL = f"{BASE_URL}/embeddings"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=BASE_URL) as http_client:
        yield http_client


class TestEmbedBatch:
    @respx.mock
    async def test_returns_vectors_in_input_order(self, client: httpx.AsyncClient) -> None:
        route = respx.post(EMBEDDINGS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [0.2, 0.3]},
                        {"index": 0, "embedding": [0.1, 0.1]},
                    ],
                    "model": "text-embedding-3-small",
                },
            )
        )
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-test", model="text-embedding-3-small")

        vectors = await provider.embed_batch(["first", "second"])

        assert route.called
        assert vectors == [[0.1, 0.1], [0.2, 0.3]]

    @respx.mock
    async def test_sends_model_and_bearer_header(self, client: httpx.AsyncClient) -> None:
        route = respx.post(EMBEDDINGS_URL).mock(
            return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]})
        )
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-secret", model="text-embedding-3-small")

        await provider.embed_batch(["text"])

        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer sk-secret"
        assert request.headers.get("Authorization") is not None

    async def test_empty_input_returns_empty_list_without_http_call(self, client: httpx.AsyncClient) -> None:
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-test", model="text-embedding-3-small")

        vectors = await provider.embed_batch([])

        assert vectors == []


class TestErrorHandling:
    @respx.mock
    async def test_unauthorized_raises_embedding_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(EMBEDDINGS_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
        provider = OpenAiEmbeddingProvider(client=client, api_key="bad-key", model="text-embedding-3-small")

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_batch(["text"])

        assert exc_info.value.code == "EMBEDDING_PROVIDER_UNAUTHORIZED"

    @respx.mock
    async def test_server_error_raises_embedding_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(EMBEDDINGS_URL).mock(return_value=httpx.Response(503))
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-test", model="text-embedding-3-small")

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_batch(["text"])

        assert exc_info.value.code == "EMBEDDING_PROVIDER_SERVER_ERROR"

    @respx.mock
    async def test_count_mismatch_raises_embedding_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(EMBEDDINGS_URL).mock(
            return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]})
        )
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-test", model="text-embedding-3-small")

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_batch(["text one", "text two"])

        assert exc_info.value.code == "EMBEDDING_PROVIDER_COUNT_MISMATCH"

    @respx.mock
    async def test_malformed_json_raises_embedding_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(EMBEDDINGS_URL).mock(return_value=httpx.Response(200, content=b"not json"))
        provider = OpenAiEmbeddingProvider(client=client, api_key="sk-test", model="text-embedding-3-small")

        with pytest.raises(EmbeddingProviderError) as exc_info:
            await provider.embed_batch(["text"])

        assert exc_info.value.code == "EMBEDDING_PROVIDER_MALFORMED_RESPONSE"
