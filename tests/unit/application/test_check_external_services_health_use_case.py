"""
Тесты `CheckExternalServicesHealthUseCase`
(application/health/use_cases/check_external_services.py, Sprint 8,
задача S8-09, ADR-8.9) — с фейковыми `ServiceHealthCheck`, без реальных
сетевых вызовов.
"""

from __future__ import annotations

import itertools

import pytest

from dekoder.application.health.ports import ServiceStatus
from dekoder.application.health.use_cases.check_external_services import CheckExternalServicesHealthUseCase


class _FakeServiceHealthCheck:
    def __init__(self, name: str, *, healthy: bool) -> None:
        self._name = name
        self._healthy = healthy

    async def check(self) -> ServiceStatus:
        detail = None if self._healthy else "boom"
        return ServiceStatus(name=self._name, healthy=self._healthy, latency_ms=1.0, detail=detail)


class _RaisingServiceHealthCheck:
    """
    Имитирует адаптер, нарушивший контракт (поднявший исключение вместо
    ServiceStatus(healthy=False)) — задача теста: подтвердить, что
    execute() падает вместе с ним (asyncio.gather без return_exceptions),
    а не молча проглатывает; корректные адаптеры (infrastructure/health/*)
    сами перехватывают исключения и сюда не долетают.
    """

    async def check(self) -> ServiceStatus:
        raise RuntimeError("adapter contract violation")


class TestAllHealthyCombination:
    async def test_all_healthy_true_when_every_check_is_healthy(self) -> None:
        use_case = CheckExternalServicesHealthUseCase(
            checks=[
                _FakeServiceHealthCheck("qdrant", healthy=True),
                _FakeServiceHealthCheck("test-provider", healthy=True),
                _FakeServiceHealthCheck("openai", healthy=True),
            ]
        )

        result = await use_case.execute()

        assert result.all_healthy is True
        assert len(result.services) == 3


class TestAllUnhealthyCombination:
    async def test_all_healthy_false_when_every_check_is_unhealthy(self) -> None:
        use_case = CheckExternalServicesHealthUseCase(
            checks=[
                _FakeServiceHealthCheck("qdrant", healthy=False),
                _FakeServiceHealthCheck("test-provider", healthy=False),
                _FakeServiceHealthCheck("openai", healthy=False),
            ]
        )

        result = await use_case.execute()

        assert result.all_healthy is False
        assert all(not service.healthy for service in result.services)


@pytest.mark.parametrize(
    "healthy_flags",
    [combo for combo in itertools.product([True, False], repeat=3) if not (all(combo) or not any(combo))],
)
async def test_all_healthy_is_false_for_every_mixed_combination(healthy_flags: tuple[bool, bool, bool]) -> None:
    """Все 8 комбинаций healthy/unhealthy: all_healthy — конъюнкция, а не «хотя бы один здоров»."""
    names = ("qdrant", "test-provider", "openai")
    use_case = CheckExternalServicesHealthUseCase(
        checks=[_FakeServiceHealthCheck(name, healthy=flag) for name, flag in zip(names, healthy_flags, strict=True)]
    )

    result = await use_case.execute()

    assert result.all_healthy is False
    assert result.all_healthy == all(healthy_flags)


class TestOneServiceRaisingDoesNotBreakTheRest:
    """
    Задача-требование S8-09: даже если один фейк поднимает исключение
    (нарушая контракт `ServiceHealthCheck.check()`, который требует
    самостоятельно перехватывать ошибки), `execute()` не должен падать
    целиком — `_run_one` перехватывает это как defense-in-depth и
    превращает в `ServiceStatus(healthy=False)`, не прерывая остальные
    проверки.
    """

    async def test_execute_does_not_raise_and_marks_the_failing_check_unhealthy(self) -> None:
        use_case = CheckExternalServicesHealthUseCase(
            checks=[
                _FakeServiceHealthCheck("qdrant", healthy=True),
                _RaisingServiceHealthCheck(),
            ]
        )

        result = await use_case.execute()  # не должно поднимать исключение

        assert result.all_healthy is False
        assert len(result.services) == 2
        healthy_names = {service.name for service in result.services if service.healthy}
        assert healthy_names == {"qdrant"}
        unhealthy = [service for service in result.services if not service.healthy]
        assert len(unhealthy) == 1
        assert "adapter contract violation" in (unhealthy[0].detail or "")
