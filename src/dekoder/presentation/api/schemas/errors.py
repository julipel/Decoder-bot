"""
Единый конверт ошибки admin REST (Sprint 8, задача S8-03, ADR-8.12) —
тело ответа, которое `presentation/api/error_handlers.py` возвращает для
любой ошибки, обработанной/необработанной.

`ErrorResponse.error.message` — всегда `exc.user_message` (безопасное
сообщение), никогда `exc.message`/`str(exc)`/traceback (`shared/errors.py`
докстринг: `message` — для журналов, `user_message` — для показа).
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
