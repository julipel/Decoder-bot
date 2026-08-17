"""
Доменная сущность `UserProfile` (Sprint 3, задача S3-02, ADR-3.5) —
запись общего сид-каталога профилей, влияющая на системную инструкцию,
передаваемую языковой модели.

Один плоский `frozen`-датакласс — по ADR-3.5 не вводятся отдельные типы
`ProfileId`/`TonePreset`/`ProfilePrompt`/`ProfilePreferences`: ни один
use case Sprint 3 не оперирует «тоном» или «настройками» отдельно от
остального профиля, единственное реально читаемое поле —
`system_instruction` (`ProcessUserMessage`, задача S3-07), остальные
описательные поля используются только для отображения в Telegram
(`/profile`, задача S3-08) и сид-данных (задача S3-04). `id: UUID` — без
обёртки, по конвенции `User.id`/`Conversation.id`/`Message.id`
(`domain/user/entities.py`, `domain/conversation/entities.py`).

`preferred_model: ModelId | None` переиспользует `domain/conversation/
value_objects.ModelId` — не дублируется.

Ноль зависимостей от SQLAlchemy/Telegram/FastAPI — чистый Python, как
`domain/user/entities.py`/`domain/conversation/entities.py`. Ошибки —
обычный `ValueError`, отдельная доменная ошибка не оправдана (claude.md
§20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.value_objects import ProfileStatus


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Запись каталога профилей — определяет системную инструкцию, применяемую к ответам пользователя."""

    id: UUID
    name: str
    description: str
    system_instruction: str
    response_style: str
    target_audience: str
    formality_level: str
    preferred_structure: str
    forbidden_phrasing: tuple[str, ...]
    preferred_model: ModelId | None
    response_length_hint: str | None
    additional_constraints: str
    status: ProfileStatus
    is_system: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name не может быть пустым")
        if not self.system_instruction.strip():
            raise ValueError("system_instruction не может быть пустым")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at не может быть раньше created_at")
