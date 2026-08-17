"""
`QdrantHealthCheck` — реализация `ServiceHealthCheck` поверх уже
открытого `AsyncQdrantClient` (Sprint 8, задача S8-09, ADR-8.9).

Переиспользует клиент, которым уже управляет `bootstrap/application.py`'s
`_lifespan` (не создаёт новый) — `client.get_collections()` под
`asyncio.wait_for` с собственным таймаутом (`AdminSettings.health_check_timeout`,
не `LLMSettings.timeout` — probe заметно короче генерации).
"""

from __future__ import annotations

import asyncio
import time

from qdrant_client import AsyncQdrantClient

from dekoder.application.health.ports import ServiceStatus

_SERVICE_NAME = "qdrant"


class QdrantHealthCheck:
    def __init__(self, client: AsyncQdrantClient, timeout: float) -> None:
        self._client = client
        self._timeout = timeout

    async def check(self) -> ServiceStatus:
        started_at = time.monotonic()
        try:
            await asyncio.wait_for(self._client.get_collections(), timeout=self._timeout)
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
