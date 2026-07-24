"""Реализация LoggerPort: структурированный вывод в stdout/stderr (docs/01, §4.8)."""

from __future__ import annotations

from dekoder.modules.logging_audit.application.ports import LoggerPort
from dekoder.modules.logging_audit.domain.entries import SystemEventEntry, TechnicalLogEvent


class StdoutTechnicalLogger(LoggerPort):
    def log_event(self, event: TechnicalLogEvent) -> None:
        raise NotImplementedError

    def log_system_error(self, entry: SystemEventEntry) -> None:
        raise NotImplementedError
