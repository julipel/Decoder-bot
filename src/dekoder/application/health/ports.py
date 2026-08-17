"""
Порты health-check внешних сервисов (Sprint 8, задача S8-09, ADR-8.9).

Новый узкий bounded-context — НЕ `application/admin/` (ADR-8.1: во
избежание коллизии с мёртвым v2.0-скелетом, дисциплина Ports & Adapters,
как и у остального проекта). `ServiceHealthCheck` — `Protocol` +
`@runtime_checkable`, тот же стиль, что `LLMProvider`/
`KnowledgeSearchService`: даёт возможность юнит-тестировать
`CheckExternalServicesHealthUseCase` с фейками без реальных сетевых
вызовов.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    healthy: bool
    latency_ms: float
    detail: str | None


@runtime_checkable
class ServiceHealthCheck(Protocol):
    """
    Каждая реализация (`infrastructure/health/*`) обязана сама
    перехватывать исключения/таймауты внутри `check()` и возвращать
    `ServiceStatus(healthy=False, ...)`, а не поднимать исключение —
    `CheckExternalServicesHealthUseCase.execute()` не должен падать из-за
    недоступности одного сервиса.
    """

    async def check(self) -> ServiceStatus: ...
