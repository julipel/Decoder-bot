"""
Logger — единый порт технических журналов, системных ошибок и аудита
(docs/versions/05, §7-8). AuditPort слит внутрь (record_audit);
AnalyticsReadPort не переносится — чтение audit-лога вне MVP (05, §5).
"""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.logging.entries import AuditRecord, SystemEventEntry, TechnicalLogEvent


class Logger(Protocol):
    def log_event(self, event: TechnicalLogEvent) -> None: ...

    def log_system_error(self, entry: SystemEventEntry) -> None: ...

    def record_audit(self, record: AuditRecord) -> None: ...
