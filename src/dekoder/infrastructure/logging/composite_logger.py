"""CompositeLogger — единственная точка, реализующая Logger целиком, делегируя в два специализированных адаптера."""

from __future__ import annotations

from dekoder.application.logging.ports import Logger
from dekoder.domain.logging.entries import AuditRecord, SystemEventEntry, TechnicalLogEvent
from dekoder.infrastructure.logging.file_audit_logger import FileAuditLogger
from dekoder.infrastructure.logging.stdout_technical_logger import StdoutTechnicalLogger


class CompositeLogger(Logger):
    def __init__(self, technical_logger: StdoutTechnicalLogger, audit_logger: FileAuditLogger) -> None:
        self._technical_logger = technical_logger
        self._audit_logger = audit_logger

    def log_event(self, event: TechnicalLogEvent) -> None:
        self._technical_logger.log_event(event)

    def log_system_error(self, entry: SystemEventEntry) -> None:
        self._technical_logger.log_system_error(entry)

    def record_audit(self, record: AuditRecord) -> None:
        self._audit_logger.record_audit(record)
