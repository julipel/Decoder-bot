"""Связь документа с кейсом (docs/01, §3, сценарий 10) — не ограничивает доступ к остальной базе знаний."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import CaseId, DocumentId


@dataclass(frozen=True)
class DocumentCaseLink:
    document_id: DocumentId
    case_id: CaseId
