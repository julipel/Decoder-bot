"""
Минимальная иерархия ошибок приложения — единственный источник истины
для исключений во всём проекте.

    DekoderError
    ├── ValidationError
    ├── ApplicationError
    ├── NotFoundError
    └── InfrastructureError
        └── ExternalServiceError
            ├── LLMProviderError
            └── EmbeddingProviderError

Подклассы добавляются только при появлении конкретного сценария
использования — не создавайте их заранее (например, отдельный класс на
каждый провайдер LLM появится вместе с адаптером этого провайдера, не раньше).

Каждая ошибка несёт:
- `code` — внутренний код (сопоставление/группировка в логах, не для
  показа пользователю); значение по умолчанию — на уровне класса,
  специфичное для конкретного сценария можно передать явно;
- `message` — техническое сообщение (для журналов/разработчиков);
- `user_message` — безопасное сообщение для пользователя, никогда не
  содержит секретов, внутренних деталей или полного текста `message`;
- `cause` — необязательная исходная ошибка (дополнительно устанавливается
  как `__cause__`, поэтому traceback сохраняет цепочку даже без `raise ... from`);
- `metadata` — необязательные структурированные данные для журналирования
  (например, `correlation_id`, `provider`) — тоже не для показа пользователю.
"""

from __future__ import annotations

from typing import Any


class DekoderError(Exception):
    """Базовая ошибка приложения — не создаётся напрямую, только через подклассы."""

    code: str = "DEKODER_ERROR"

    def __init__(
        self,
        message: str,
        user_message: str,
        *,
        code: str | None = None,
        cause: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.user_message = user_message
        if code is not None:
            self.code = code
        self.cause = cause
        self.metadata = metadata if metadata is not None else {}
        if cause is not None:
            self.__cause__ = cause

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(DekoderError):
    """Входные данные не прошли проверку."""

    code = "VALIDATION_ERROR"


class ApplicationError(DekoderError):
    """Ошибка бизнес-логики / use case'а."""

    code = "APPLICATION_ERROR"


class NotFoundError(DekoderError):
    """
    Запрошенный ресурс не существует (Sprint 8, admin REST, ADR-8.12) —
    сиблинг `ValidationError`/`ApplicationError`/`InfrastructureError`,
    не подкласс. Use case'ы, уже возвращающие `None` на «не найдено»
    (`SelectProfile`/`GetActiveProfile` и т.п.), сами эту ошибку не
    поднимают — её поднимает вызывающий REST-роут, транслируя `None` в
    404 (`presentation/api/error_handlers.py`).
    """

    code = "NOT_FOUND"


class InfrastructureError(DekoderError):
    """Ошибка инфраструктурного слоя (хранилище, файловая система, сеть)."""

    code = "INFRASTRUCTURE_ERROR"


class ExternalServiceError(InfrastructureError):
    """Ошибка при обращении к внешнему сервису."""

    code = "EXTERNAL_SERVICE_ERROR"


class LLMProviderError(ExternalServiceError):
    """Ошибка при обращении к провайдеру генеративной модели."""

    code = "LLM_PROVIDER_ERROR"


class EmbeddingProviderError(ExternalServiceError):
    """Ошибка при обращении к провайдеру эмбеддингов (Sprint 6, ADR-6.3) — не `LLMProviderError`, другой сервис."""

    code = "EMBEDDING_PROVIDER_ERROR"
