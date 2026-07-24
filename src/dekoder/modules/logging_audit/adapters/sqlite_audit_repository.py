"""Реализация AuditPort: отдельная таблица SQLite (docs/01, §4.8)."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.modules.logging_audit.application.ports import AuditPort
from dekoder.modules.logging_audit.domain.entries import AuditEntry


class SqliteAuditRepository(AuditPort):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def record(self, entry: AuditEntry) -> None:
        raise NotImplementedError
