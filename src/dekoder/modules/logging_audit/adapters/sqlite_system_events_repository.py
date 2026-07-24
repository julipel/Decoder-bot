"""Реализация AnalyticsReadPort и хранения системных событий/ошибок (docs/01, §4.8; docs/02, §12)."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.modules.logging_audit.application.ports import AnalyticsReadPort
from dekoder.modules.logging_audit.domain.entries import SystemEventEntry, TechnicalLogEvent


class SqliteSystemEventsRepository(AnalyticsReadPort):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def save(self, entry: SystemEventEntry) -> None:
        raise NotImplementedError

    def read_since(self, correlation_id: CorrelationId | None) -> list[TechnicalLogEvent]:
        raise NotImplementedError
