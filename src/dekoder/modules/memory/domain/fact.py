"""Подтверждённый пользовательский факт (docs/01, §4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import FactId, UserId


@dataclass
class Fact:
    """Факт сохраняется только после явного подтверждения пользователем."""

    fact_id: FactId
    user_id: UserId
    text: str
    confirmed_at: datetime
