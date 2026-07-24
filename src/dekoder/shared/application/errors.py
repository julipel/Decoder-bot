"""
Базовые исключения уровня application, общие для всех модулей.

Модули наследуются от этих классов вместо бытовых исключений
(ValueError, KeyError) — это даёт driving adapters (Telegram, HTTP)
единый способ сопоставить ошибку с ответом пользователю, не зная
внутренних деталей конкретного модуля.
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
