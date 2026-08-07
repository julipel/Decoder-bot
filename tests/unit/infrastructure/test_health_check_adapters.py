"""
Тесты адаптеров `ServiceHealthCheck` (infrastructure/health/*, Sprint 8,
задача S8-09, ADR-8.9) — OpenRouter/OpenAI через `respx` (реальный
сетевой вызов никогда не происходит), Qdrant — через минимальный
duck-typed фейк с `get_collections()`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from dekoder.infrastructure.health.openai_health_check import OpenAiHealthCheck
from dekoder.infrastructure.health.openrouter_health_check import OpenRouterHealthCheck
from dekoder.infrastructure.health.qdrant_health_check import QdrantHealthCheck


class _FakeQdrantClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail

    async def get_collections(self) -> object:
        if self._should_fail:
            raise RuntimeError("connection refused")
        return object()


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url="https://example.test") as client:
        yield client


class TestQdrantHealthCheck:
    async def test_healthy_when_get_collections_succeeds(self) -> None:
        check = QdrantHealthCheck(client=_FakeQdrantClient(should_fail=False), timeout=1.0)  # type: ignore[arg-type]

        status = await check.check()

        assert status.healthy is True
        assert status.name == "qdrant"
        assert status.detail is None

    async def test_unhealthy_when_get_collections_raises(self) -> None:
        check = QdrantHealthCheck(client=_FakeQdrantClient(should_fail=True), timeout=1.0)  # type: ignore[arg-type]

        status = await check.check()

        assert status.healthy is False
        assert status.detail is not None
        assert "connection refused" in status.detail


class TestOpenRouterHealthCheck:
    @respx.mock
    async def test_healthy_on_200(self, http_client: httpx.AsyncClient) -> None:
        respx.get("https://example.test/models").mock(return_value=httpx.Response(200, json={"data": []}))
        check = OpenRouterHealthCheck(client=http_client, api_key="sk-test", timeout=1.0)

        status = await check.check()

        assert status.healthy is True
        assert status.name == "openrouter"

    @respx.mock
    async def test_unhealthy_on_500(self, http_client: httpx.AsyncClient) -> None:
        respx.get("https://example.test/models").mock(return_value=httpx.Response(500))
        check = OpenRouterHealthCheck(client=http_client, api_key="sk-test", timeout=1.0)

        status = await check.check()

        assert status.healthy is False
        assert status.detail is not None

    @respx.mock
    async def test_unhealthy_on_connection_error(self, http_client: httpx.AsyncClient) -> None:
        respx.get("https://example.test/models").mock(side_effect=httpx.ConnectError("refused"))
        check = OpenRouterHealthCheck(client=http_client, api_key="sk-test", timeout=1.0)

        status = await check.check()

        assert status.healthy is False


class TestOpenAiHealthCheck:
    @respx.mock
    async def test_healthy_on_200(self, http_client: httpx.AsyncClient) -> None:
        respx.get("https://example.test/models").mock(return_value=httpx.Response(200, json={"data": []}))
        check = OpenAiHealthCheck(client=http_client, api_key="sk-test", timeout=1.0)

        status = await check.check()

        assert status.healthy is True
        assert status.name == "openai"

    @respx.mock
    async def test_unhealthy_on_401(self, http_client: httpx.AsyncClient) -> None:
        respx.get("https://example.test/models").mock(return_value=httpx.Response(401))
        check = OpenAiHealthCheck(client=http_client, api_key="sk-test", timeout=1.0)

        status = await check.check()

        assert status.healthy is False
        assert status.detail is not None

    @respx.mock
    async def test_sends_bearer_authorization_header(self, http_client: httpx.AsyncClient) -> None:
        route = respx.get("https://example.test/models").mock(return_value=httpx.Response(200, json={"data": []}))
        check = OpenAiHealthCheck(client=http_client, api_key="sk-secret", timeout=1.0)

        await check.check()

        assert route.calls.last.request.headers["Authorization"] == "Bearer sk-secret"
