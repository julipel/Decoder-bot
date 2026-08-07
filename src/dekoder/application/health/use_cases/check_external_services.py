"""
`CheckExternalServicesHealthUseCase` — параллельно опрашивает все
зарегистрированные `ServiceHealthCheck` (Sprint 8, задача S8-09,
ADR-8.9).

Каждый адаптер (`infrastructure/health/*`) обязан сам перехватывать
исключения/таймауты и возвращать `ServiceStatus(healthy=False, ...)`, не
поднимать исключение — но `_run_one` дополнительно оборачивает вызов
собственным `try/except` (defense in depth): нарушение контракта одним
адаптером (баг, не предусмотренный сценарий) не должно ронять
`asyncio.gather` целиком и лишать ответ данных об остальных, уже
опрошенных сервисах. Тот же принцип деградации, что
`ProcessUserMessage._search_knowledge` — недоступность внешнего сервиса
здесь тоже штатный, не ошибочный исход.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from dekoder.application.health.ports import ServiceHealthCheck, ServiceStatus
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class ExternalServicesHealthResult:
    services: tuple[ServiceStatus, ...]
    all_healthy: bool


class CheckExternalServicesHealthUseCase:
    def __init__(self, checks: Sequence[ServiceHealthCheck]) -> None:
        self._checks = checks

    async def execute(self) -> ExternalServicesHealthResult:
        results = await asyncio.gather(*(self._run_one(check) for check in self._checks))
        all_healthy = all(result.healthy for result in results)
        return ExternalServicesHealthResult(services=tuple(results), all_healthy=all_healthy)

    @staticmethod
    async def _run_one(check: ServiceHealthCheck) -> ServiceStatus:
        try:
            return await check.check()
        except Exception as exc:
            name = getattr(check, "name", None) or type(check).__name__
            _logger.error("service_health_check_adapter_raised", service=name, error=str(exc))
            return ServiceStatus(name=name, healthy=False, latency_ms=0.0, detail=str(exc))
