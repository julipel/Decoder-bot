"""
`OpenAiHealthCheck` — реализация `ServiceHealthCheck` поверх уже
открытого `httpx.AsyncClient` (Sprint 8, задача S8-09, ADR-8.9) — того
же клиента, что использует `OpenAiEmbeddingProvider` (переиспользуется,
не создаётся заново).

`GET /models`, `Authorization: Bearer {api_key}` — дешёвый способ
подтвердить одновременно и доступность провайдера эмбеддингов, и
валидность ключа, не тратя реальный embeddings-запрос.

`service_name` — конструкторный параметр, не хардкод-константа модуля
(2026-08-13, вслед за переключением эмбеддингов на RouterAI, тем же
приёмом, что уже применён к `OpenAiCompatibleHealthCheck`, ADR-11.1) —
иначе `/admin/health` продолжал бы называть проверку "openai" даже когда
`EMBEDDING_PROVIDER_BASE_URL` указывает на другого агрегатора.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from dekoder.application.health.ports import ServiceStatus

_MODELS_PATH = "/models"


class OpenAiHealthCheck:
    def __init__(self, client: httpx.AsyncClient, api_key: str, timeout: float, service_name: str = "openai") -> None:
        self._client = client
        self._api_key = api_key
        self._timeout = timeout
        self._service_name = service_name

    async def check(self) -> ServiceStatus:
        started_at = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._client.get(_MODELS_PATH, headers={"Authorization": f"Bearer {self._api_key}"}),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            return ServiceStatus(
                name=self._service_name,
                healthy=False,
                latency_ms=(time.monotonic() - started_at) * 1000,
                detail=str(exc),
            )
        return ServiceStatus(
            name=self._service_name,
            healthy=True,
            latency_ms=(time.monotonic() - started_at) * 1000,
            detail=None,
        )
