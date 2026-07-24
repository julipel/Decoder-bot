"""
Черновик факта, ожидающий подтверждения (docs/02, §16.3).

Место хранения черновика не было зафиксировано в docs/01 — решение
хранить его в SQLite с ограниченным сроком жизни принято в docs/02.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import FactDraftId, UserId


@dataclass
class FactDraft:
    """Черновик факта: существует до подтверждения или истечения срока."""

    draft_id: FactDraftId
    user_id: UserId
    text: str
    created_at: datetime
    expires_at: datetime
