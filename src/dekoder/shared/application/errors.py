"""
Иерархия ошибок application-слоя (docs/versions/05, §12 — концептуальные
категории, не привязанные к HTTP-кодам или конкретным типам исключений).

Базовые 4 класса — как в v1; UnavailableError — новая база для
транзиентных/инфраструктурных ошибок, отличных от бизнес-конфликтов.
14 именованных подклассов покрывают ровно 14 строк таблицы `05`, §12.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Базовое исключение use case'ов."""


class NotFoundError(ApplicationError):
    """Запрошенная сущность не найдена."""


class ValidationError(ApplicationError):
    """Входные данные не прошли проверку на уровне use case."""


class ConflictError(ApplicationError):
    """Операция конфликтует с текущим состоянием сущности."""


class UnavailableError(ApplicationError):
    """Транзиентная недоступность внешнего порта/адаптера."""


class ProfileNotFound(NotFoundError):
    pass


class SkillNotFound(NotFoundError):
    pass


class SessionNotFound(NotFoundError):
    pass


class ProfileArchived(ConflictError):
    pass


class ProfileLimitExceeded(ConflictError):
    pass


class SessionExpired(ConflictError):
    pass


class MemoryConflict(ConflictError):
    pass


class SkillIncompatible(ValidationError):
    pass


class ModelIncompatible(ValidationError):
    pass


class ModelUnavailable(UnavailableError):
    pass


class KnowledgeUnavailable(UnavailableError):
    pass


class Timeout(UnavailableError):
    pass


class AuthenticationFailed(ApplicationError):
    pass
