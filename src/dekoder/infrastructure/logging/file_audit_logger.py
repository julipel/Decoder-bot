"""
Append-only JSONL-файл аудита — не SQLite, чтобы не создавать запрещённую
зависимость infrastructure/logging -> infrastructure/persistence.
Оправдано отсутствием GetAuditLogQuery в MVP (docs/versions/05, §5) —
аудит только пишется, никогда не читается обратно приложением.
"""

from __future__ import annotations

from dekoder.domain.logging.entries import AuditRecord


class FileAuditLogger:
    """Реализует половину Logger (record_audit); технические журналы — StdoutTechnicalLogger."""

    def __init__(self, audit_log_path: str) -> None:
        self._audit_log_path = audit_log_path

    def record_audit(self, record: AuditRecord) -> None:
        raise NotImplementedError
