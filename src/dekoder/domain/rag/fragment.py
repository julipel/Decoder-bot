"""
KnowledgeFragment — самостоятельный агрегат, ссылается на источник
только по id; неизменяем (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dekoder.shared.domain.identifiers import CaseId, DocumentId, FragmentId


class FragmentSourceType(str, Enum):
    DOCUMENT = "document"
    CASE = "case"


@dataclass(frozen=True)
class KnowledgeFragment:
    fragment_id: FragmentId
    source_type: FragmentSourceType
    source_id: DocumentId | CaseId
    text: str
    score: float | None = None
