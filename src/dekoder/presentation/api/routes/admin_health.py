"""
`admin_health_router` — защищённый `GET /admin/health` с реальными
проверками Qdrant/LLM-провайдера/OpenAI (Sprint 8, задача S8-09, ADR-8.9).

Не путать с публичным `GET /health` (`composition/health.py`) — тот
остаётся дешёвым, без auth, без сети (Docker healthcheck опрашивает его
каждые 30с). Этот эндпоинт защищён `require_admin_api_key`, делает
реальные сетевые вызовы и всегда возвращает 200 (даже если все три
сервиса недоступны — `all_healthy=false`, а не 5xx: недоступность
внешнего сервиса не равна сбою самого admin-эндпоинта, ADR-8.9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dekoder.bootstrap.application import get_container
from dekoder.bootstrap.container import ApplicationContainer
from dekoder.presentation.api.dependencies.auth import require_admin_api_key
from dekoder.presentation.api.schemas.health import ExternalServicesHealthResponse, ServiceStatusResponse

router = APIRouter(prefix="/admin", tags=["admin-health"], dependencies=[Depends(require_admin_api_key)])


@router.get("/health", response_model=ExternalServicesHealthResponse)
async def get_admin_health(
    container: ApplicationContainer = Depends(get_container),
) -> ExternalServicesHealthResponse:
    result = await container.check_external_services_health.execute()
    return ExternalServicesHealthResponse(
        services=[
            ServiceStatusResponse(name=s.name, healthy=s.healthy, latency_ms=s.latency_ms, detail=s.detail)
            for s in result.services
        ],
        all_healthy=result.all_healthy,
    )
