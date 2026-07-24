"""
Записи журналов (docs/01, §4.8): технические события, аудит, системные
события/ошибки. Полный текст диалога сюда не входит — он остаётся в
memory (docs/02, §14).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import CorrelationId


@dataclass(frozen=True)
class TechnicalLogEvent:
    """Только идентификатор запроса и статус — без текста реплик (docs/02, §14)."""

    correlation_id: CorrelationId
    event: str
    status: str
    occurred_at: datetime


@dataclass(frozen=True)
class AuditEntry:
    """Действие администратора: загрузка/изменение/удаление документа или кейса (docs/01, §4.8)."""

    correlation_id: CorrelationId
    action: str
    occurred_at: datetime


@dataclass(frozen=True)
class SystemEventEntry:
    """Ошибка, требующая последующего анализа (docs/01, §4.8)."""

    correlation_id: CorrelationId
    description: str
    occurred_at: datetime
