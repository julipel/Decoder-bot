"""
Фрагмент документа/кейса (docs/02, §2 — домен Fragment).

Один класс используется и при индексации (без score), и как результат
поиска (со score) — отдельный DTO для этого избыточен для MVP.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dekoder.shared.domain.identifiers import CaseId, DocumentId, FragmentId


class FragmentSourceType(str, Enum):
    DOCUMENT = "document"
    CASE = "case"


@dataclass(frozen=True)
class Fragment:
    fragment_id: FragmentId
    source_type: FragmentSourceType
    source_id: DocumentId | CaseId
    text: str
    score: float | None = None
