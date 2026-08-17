"""
CLI-скрипт проверки доступности внешних сервисов (Sprint 8, задача
S8-10, ADR-8.9/8.11) — тонкая обёртка над `CheckExternalServicesHealthUseCase`
(`application/health/use_cases/check_external_services.py`, S8-09), той
же композиции адаптеров (`infrastructure/health/*`), что и `GET
/admin/health`, но без HTTP/auth-слоя: не проверяет admin API key — CLI-
скрипты и так требуют доступа к `.env`/файловой системе сервера (ADR-8.11).

Использование:
    python scripts/check_services.py

Печатает статус каждого сервиса (Qdrant/LLM-провайдер/OpenAI), exit code
`0`, если все здоровы (`all_healthy`), иначе `1` — пригодно для
скриптования (`python scripts/check_services.py; echo $?`,
health-проверка в CI/деплое).

Собирает те же три клиента, что `bootstrap/application.py`/
`telegram_main.py` (`build_qdrant_client`, два `httpx.AsyncClient`) —
никакого обращения к БД (health-check не требует БД вообще, ADR-8.4).
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from dekoder.application.health.use_cases.check_external_services import CheckExternalServicesHealthUseCase
from dekoder.infrastructure.health.openai_compatible_health_check import OpenAiCompatibleHealthCheck
from dekoder.infrastructure.health.openai_health_check import OpenAiHealthCheck
from dekoder.infrastructure.health.qdrant_health_check import QdrantHealthCheck
from dekoder.infrastructure.qdrant.client import build_qdrant_client
from dekoder.shared.config import Settings
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


async def _run_check(settings: Settings) -> int:
    qdrant_client = build_qdrant_client(settings.qdrant)
    timeout = settings.admin.health_check_timeout
    try:
        async with (
            httpx.AsyncClient(base_url=settings.llm_provider.base_url, timeout=settings.llm.timeout) as http_client,
            httpx.AsyncClient(
                base_url=settings.embedding_provider.base_url, timeout=settings.llm.timeout
            ) as embedding_http_client,
        ):
            use_case = CheckExternalServicesHealthUseCase(
                checks=[
                    QdrantHealthCheck(client=qdrant_client, timeout=timeout),
                    OpenAiCompatibleHealthCheck(
                        client=http_client,
                        api_key=settings.llm_provider.api_key.get_secret_value(),
                        service_name=settings.llm_provider.provider_id,
                        timeout=timeout,
                    ),
                    OpenAiHealthCheck(
                        client=embedding_http_client,
                        api_key=settings.embedding_provider.api_key.get_secret_value(),
                        timeout=timeout,
                        service_name="embedding_provider",
                    ),
                ]
            )
            result = await use_case.execute()
    finally:
        await qdrant_client.close()

    for service in result.services:
        status = "OK" if service.healthy else "UNAVAILABLE"
        detail = f" ({service.detail})" if service.detail else ""
        print(f"{service.name:12} {status:12} {service.latency_ms:8.1f}ms{detail}")

    return 0 if result.all_healthy else 1


def main() -> None:
    settings = Settings()
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )
    _logger.info("external_services_check_started")
    exit_code = asyncio.run(_run_check(settings))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
