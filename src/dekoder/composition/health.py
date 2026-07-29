"""
Системный health-check (docs/03, §3 не привязывает его ни к одному
бизнес-модулю — это ASGI-уровень, а не use case). Живёт в `composition/`,
единственном пакете, для которого docs/03, §5 делает исключение из
правила «application/domain не импортируют FastAPI».
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

APP_NAME = "dekoder"
APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service=APP_NAME, version=APP_VERSION)
