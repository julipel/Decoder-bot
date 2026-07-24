"""
Кейс (docs/01, §3): структурированный пример выполнения задачи — исходные
данные, тип задачи, ожидаемый подход, пример результата. Не клиентский
проект и не отдельная база знаний.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dekoder.shared.domain.identifiers import CaseId


class CaseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Case:
    case_id: CaseId
    title: str
    input_data: str
    task_type: str
    expected_approach: str
    example_result: str
    status: CaseStatus = CaseStatus.ACTIVE
