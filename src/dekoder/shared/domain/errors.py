"""Базовые исключения уровня domain, общие для всех модулей."""

from __future__ import annotations


class DomainError(Exception):
    """Нарушение инварианта доменной модели."""
