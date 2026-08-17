"""
Доменная сущность `MemoryRecord` (Sprint 5, задача S5-02, ADR-5.2/ADR-5.3)
— запись контролируемой долговременной памяти пользователя, реализующая
Этап 7 «Плана реализации.md».

Один плоский `frozen`-датакласс, стиль `domain/profile/entities.py::
UserProfile`. `id`/`user_id: UUID` — без обёртки, по конвенции
`User.id`/`Conversation.id`/`Message.id`/`UserProfile.id`: ни одна живая
сущность проекта не использует `NewType`-обёртки из мёртвого
`shared/domain/identifiers.py` (ADR-5.2), этот модуль не импортируется.

Ноль зависимостей от SQLAlchemy/Telegram/FastAPI — чистый Python, как
`domain/profile/entities.py`. Ошибки — обычный `ValueError`, отдельная
доменная ошибка не оправдана (claude.md §20, по прецеденту `UserProfile`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """Запись долговременной памяти — подтверждённый факт о пользователе, используемый секцией 4 промпта."""

    id: UUID
    user_id: UUID
    text: str
    category: MemoryCategory
    source: MemorySource
    status: MemoryStatus
    confidence: MemoryConfidence
    is_sensitive: bool
    expires_at: datetime | None
    updated_by: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text не может быть пустым")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at не может быть раньше created_at")
