from __future__ import annotations

from dekoder.domain.logging.entries import SystemEventEntry, TechnicalLogEvent


class StdoutTechnicalLogger:
    """Реализует половину Logger (log_event/log_system_error); аудит — FileAuditLogger."""

    def log_event(self, event: TechnicalLogEvent) -> None:
        raise NotImplementedError

    def log_system_error(self, entry: SystemEventEntry) -> None:
        raise NotImplementedError
