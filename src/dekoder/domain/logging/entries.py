"""Записи технического журнала, системных событий и аудита (docs/versions/04, §4; §11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import AuditRecordId, CorrelationId


@dataclass(frozen=True)
class TechnicalLogEvent:
    correlation_id: CorrelationId
    event: str
    status: str
    occurred_at: datetime


@dataclass(frozen=True)
class SystemEventEntry:
    correlation_id: CorrelationId
    description: str
    occurred_at: datetime


@dataclass(frozen=True)
class AuditRecord:
    """Entity, не Value Object — собственная идентичность, чтобы отличать записи с совпадающим содержимым (04)."""

    record_id: AuditRecordId
    correlation_id: CorrelationId
    action: str
    occurred_at: datetime
