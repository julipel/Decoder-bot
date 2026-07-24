"""
Порты журналирования (docs/02, §7).

AnalyticsReadPort — точка расширения для будущего аналитического модуля
(docs/02, §12): доменная логика аналитики не должна зависеть от структуры
таблиц SQLite, поэтому контракт объявлен здесь, а не как прямой доступ к
SQLite.
"""

from __future__ import annotations

from typing import Protocol

from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.modules.logging_audit.domain.entries import AuditEntry, SystemEventEntry, TechnicalLogEvent


class LoggerPort(Protocol):
    """Технические журналы: stdout/stderr + системные события/ошибки (docs/01, §4.8)."""

    def log_event(self, event: TechnicalLogEvent) -> None: ...

    def log_system_error(self, entry: SystemEventEntry) -> None: ...


class AuditPort(Protocol):
    """Аудит административных действий."""

    def record(self, entry: AuditEntry) -> None: ...


class AnalyticsReadPort(Protocol):
    """
    Обезличенные записи о взаимодействиях для будущего аналитического
    модуля (docs/02, §12). Конкретная реализация может читать SQLite, но
    контракт от структуры таблиц не зависит.
    """

    def read_since(self, correlation_id: CorrelationId | None) -> list[TechnicalLogEvent]: ...
