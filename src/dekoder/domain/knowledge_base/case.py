"""
KnowledgeCase — структурированный пример выполнения задачи; не удаляется
физически, только архивируется (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dekoder.shared.domain.identifiers import CaseId


class CaseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class KnowledgeCase:
    case_id: CaseId
    title: str
    input_data: str
    task_type: str
    expected_approach: str
    example_result: str
    status: CaseStatus = CaseStatus.ACTIVE
