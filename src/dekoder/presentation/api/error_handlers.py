"""
Единый обработчик ошибок admin REST (Sprint 8, задача S8-03, ADR-8.12).

Регистрируется глобально в `bootstrap/application.py::create_application`
(не только на admin-роутерах) — распространяется на все текущие и
будущие REST-роуты. `GET /health` не поднимает `DekoderError`, поэтому
безвреден для него — контракт публичного эндпоинта не меняется.

`dekoder_error_handler` никогда не отдаёт `exc.message`/`str(exc)`/
traceback клиенту — только `exc.user_message` (см. `shared/errors.py`
докстринг). `unhandled_exception_handler` перехватывает любое непойманное
исключение (500, нейтральное тело), но полный traceback остаётся в
логах через `_logger.exception` (не теряется, просто не долетает до
HTTP-ответа).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from dekoder.presentation.api.schemas.errors import ErrorDetail, ErrorResponse
from dekoder.shared.errors import ApplicationError, DekoderError, InfrastructureError, NotFoundError, ValidationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

# code -> статус-код: override по конкретному коду ошибки, приоритетнее
# маппинга по типу ниже. Единственный текущий пример — ADR-8.8:
# PROFILE_ARCHIVE_DEFAULT_FORBIDDEN — конфликт с текущим состоянием
# ресурса (409), а не общая ошибка бизнес-логики (400), которую иначе
# получил бы любой ApplicationError.
_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN": 409,
}

# Порядок не важен для корректности (типы не пересекаются как сиблинги),
# но проверяется по порядку ниже; InfrastructureError матчит через
# isinstance также все свои подклассы (ExternalServiceError/
# LLMProviderError/EmbeddingProviderError) без отдельных записей.
_STATUS_BY_ERROR_TYPE: tuple[tuple[type[DekoderError], int], ...] = (
    (ValidationError, 422),
    (NotFoundError, 404),
    (InfrastructureError, 502),
    (ApplicationError, 400),
)


def _resolve_status_code(exc: DekoderError) -> int:
    override = _STATUS_BY_ERROR_CODE.get(exc.code)
    if override is not None:
        return override
    for error_type, status_code in _STATUS_BY_ERROR_TYPE:
        if isinstance(exc, error_type):
            return status_code
    return 500


async def dekoder_error_handler(request: Request, exc: DekoderError) -> JSONResponse:
    status_code = _resolve_status_code(exc)
    _logger.warning("admin_request_failed", code=exc.code, status_code=status_code, path=request.url.path)
    body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.user_message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _logger.exception("admin_request_unhandled_error", path=request.url.path)
    body = ErrorResponse(error=ErrorDetail(code="INTERNAL_ERROR", message="Внутренняя ошибка сервера."))
    return JSONResponse(status_code=500, content=body.model_dump())
