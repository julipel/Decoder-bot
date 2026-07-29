"""
MemoryFactDraft — временный черновик факта, ожидающий подтверждения;
существует не дольше TTL (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dekoder.shared.domain.identifiers import DraftId, UserId


@dataclass
class MemoryFactDraft:
    draft_id: DraftId
    user_id: UserId
    text: str
    created_at: datetime
    expires_at: datetime
