"""
`OpenAiCompatibleHealthCheck` — реализация `ServiceHealthCheck` поверх уже
открытого `httpx.AsyncClient` (Sprint 8, задача S8-09, ADR-8.9) — того
же клиента, что использует `OpenAiCompatibleLLMAdapter` (переиспользуется,
не создаётся заново).

Sprint 11 (задача S11-01, ADR-11.1): обобщён с прежнего
`OpenRouterHealthCheck` — `service_name` больше не хардкод-константа
модуля, а обязательный конструкторный параметр (значение приходит из
`LLM_PROVIDER_PROVIDER_ID`, тем же приёмом, что `provider_id` у
`OpenAiCompatibleLLMAdapter`).

`GET /models` — конвенция самого OpenAI Chat Completions API, публичный,
дешёвый эндпоинт каталога моделей, не требующий полноценного вызова
генерации для проверки доступности. Это допущение, не подтверждённое
против ещё не выбранного пользователем реального агрегатора — если у
выбранного сервиса такого эндпоинта нет, health-check будет ошибочно
репортить unhealthy (см. README/ADR-11.1, известное ограничение).
"""

from __future__ import annotations

import asyncio
import time

import httpx

from dekoder.application.health.ports import ServiceStatus

_MODELS_PATH = "/models"


class OpenAiCompatibleHealthCheck:
    def __init__(self, client: httpx.AsyncClient, api_key: str, service_name: str, timeout: float) -> None:
        self._client = client
        self._api_key = api_key
        self._service_name = service_name
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
