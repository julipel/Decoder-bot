"""
Структурированное логирование (structlog), минимальная конфигурация.

Каждая запись журнала — JSON-строка в stdout с обязательными полями
`timestamp`, `level`, `event`, `logger`, `environment`. При обработке
запроса допускается добавление `correlation_id`, `provider`, `model`,
`duration` — через `bind_request_context()` (contextvars, живёт до
`clear_request_context()`) либо как именованные аргументы вызова лога.

Не логируются (redaction-процессор — защитный барьер, а не единственная
линия защиты: вызывающий код не должен передавать эти значения вовсе):
API-ключи, Telegram token, полный текст пользовательского сообщения,
полный ответ модели, HTTP Authorization header.

`configure_logging()` не вызывается при импорте этого модуля — конфигурация
происходит один раз в bootstrap-слое (`composition/bootstrap.py`), как и
`Settings()` (`shared/config.py`).
"""

from __future__ import annotations

from typing import Any

import structlog
from structlog.typing import EventDict, Processor

# Точные имена ключей, которые нельзя показывать в журнале открытым текстом.
# Защитный барьер поверх дисциплины вызывающего кода, а не замена ей.
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "openrouter_api_key",
        "yandexgpt_api_key",
        "openai_api_key",
        "bot_token",
        "telegram_bot_token",
        "webhook_secret",
        "telegram_webhook_secret",
        "authorization",
        "http_authorization",
        "auth_header",
        "message",
        "user_message",
        "message_text",
        "response",
        "model_response",
        "generated_text",
        "answer_text",
        "password",
        "admin_password_hash",
        "secret",
        "session_secret",
    }
)

_REDACTED = "***REDACTED***"


def _redact_sensitive_fields(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    for key in event_dict:
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


def _bind_environment(environment: str) -> Processor:
    def processor(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("environment", environment)
        return event_dict

    return processor


def configure_logging(environment: str, level: str = "INFO") -> None:
    """Настраивает structlog на JSON-вывод в stdout. Вызывается один раз при старте процесса."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            _bind_environment(environment),
            _redact_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Логгер с привязанным полем `logger` (имя модуля/компонента)."""
    return structlog.get_logger(name).bind(logger=name)


def bind_request_context(
    *,
    correlation_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    duration: float | None = None,
) -> None:
    """
    Привязывает необязательные поля обработки запроса к текущему контексту
    (contextvars) — попадут во все последующие записи журнала в этом
    контексте выполнения, пока не будет вызван `clear_request_context()`.
    """
    fields = {
        "correlation_id": correlation_id,
        "provider": provider,
        "model": model,
        "duration": duration,
    }
    structlog.contextvars.bind_contextvars(**{k: v for k, v in fields.items() if v is not None})


def clear_request_context() -> None:
    """Снимает все поля, привязанные `bind_request_context()`."""
    structlog.contextvars.clear_contextvars()
