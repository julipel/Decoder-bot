"""
Pydantic-схемы ответа `GET /admin/health` (Sprint 8, задача S8-09,
ADR-8.9).
"""

from __future__ import annotations

from pydantic import BaseModel


class ServiceStatusResponse(BaseModel):
    name: str
    healthy: bool
    latency_ms: float
    detail: str | None


class ExternalServicesHealthResponse(BaseModel):
    services: list[ServiceStatusResponse]
    all_healthy: bool
