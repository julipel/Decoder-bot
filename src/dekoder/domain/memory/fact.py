"""
MemoryFact — один подтверждённый факт о пользователе; текст не
редактируется после создания (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import FactId, UserId


@dataclass
class MemoryFact:
    fact_id: FactId
    user_id: UserId
    text: str
    confirmed_at: datetime
