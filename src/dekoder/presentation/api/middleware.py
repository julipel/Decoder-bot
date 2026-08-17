"""
`CorrelationIdMiddleware` — сквозная трассировка admin REST (Sprint 9,
задача S9-03, ADR-9.3).

Единственный ASGI-middleware проекта: читает заголовок `X-Correlation-Id`
входящего запроса (если клиент уже передал свой ID — переиспользуется,
не перезаписывается), иначе генерирует новый прямым `uuid.uuid4()` — тот
же способ, что уже принят в `presentation/telegram/mapper.py::to_command()`,
не через мёртвый `shared/utils/correlation.py::UuidCorrelationIdGenerator`.

Привязывает `correlation_id` к контексту логирования на время обработки
запроса (`bind_request_context()`/`clear_request_context()`, `shared/
logging.py`, `contextvars`) — тем же приёмом, что и `TextMessageHandler`/
все обработчики Telegram (S9-02). Благодаря этому `presentation/api/
error_handlers.py::dekoder_error_handler`/`unhandled_exception_handler`
(Sprint 8, ADR-8.12) автоматически получают `correlation_id` в своих
логах без каких-либо изменений в самих обработчиках — `bind_request_
context()` уже действует к моменту их вызова.

Регистрируется один раз на всё приложение в `bootstrap/application.py::
create_application()` — не по одному middleware на роутер. Действует на
все роуты, включая `GET /health`: не меняет тело/статус ответа, только
добавляет заголовок `X-Correlation-Id` в ответ и контекст логирования.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from dekoder.shared.logging import bind_request_context, clear_request_context

CORRELATION_ID_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        bind_request_context(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
