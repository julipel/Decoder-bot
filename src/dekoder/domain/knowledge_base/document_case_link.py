"""
DocumentCaseLink — association many-to-many между KnowledgeDocument и
KnowledgeCase, без владения ни одной стороной (docs/versions/04, §7).
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import CaseId, DocumentId


@dataclass(frozen=True)
class DocumentCaseLink:
    document_id: DocumentId
    case_id: CaseId
