"""
`OpenRouterHealthCheck` — реализация `ServiceHealthCheck` поверх уже
открытого `httpx.AsyncClient` (Sprint 8, задача S8-09, ADR-8.9) — того
же клиента, что использует `OpenRouterLLMAdapter` (переиспользуется, не
создаётся заново).

`GET /models` — публичный, дешёвый эндпоинт каталога моделей OpenRouter,
не требующий полноценного вызова генерации для проверки доступности.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from dekoder.application.health.ports import ServiceStatus

_SERVICE_NAME = "openrouter"
_MODELS_PATH = "/models"


class OpenRouterHealthCheck:
    def __init__(self, client: httpx.AsyncClient, api_key: str, timeout: float) -> None:
        self._client = client
        self._api_key = api_key
        self._timeout = timeout

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
                name=_SERVICE_NAME,
                healthy=False,
                latency_ms=(time.monotonic() - started_at) * 1000,
                detail=str(exc),
            )
        return ServiceStatus(
            name=_SERVICE_NAME,
            healthy=True,
            latency_ms=(time.monotonic() - started_at) * 1000,
            detail=None,
        )
