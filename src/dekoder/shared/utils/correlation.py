"""
Генератор идентификатора трассировки операции (docs/versions/05, §8):
кросс-модульная утилита, не привязанная ни к одному компоненту `02`.
"""

from __future__ import annotations

from typing import Protocol

from dekoder.shared.domain.identifiers import CorrelationId


class CorrelationIdGenerator(Protocol):
    def generate(self) -> CorrelationId: ...


class UuidCorrelationIdGenerator:
    def generate(self) -> CorrelationId:
        raise NotImplementedError
