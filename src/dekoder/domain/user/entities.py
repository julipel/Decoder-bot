"""
Доменная сущность `User` (Sprint 2, задача S2-02) — владелец диалогов.

`User` не содержит бизнес-логики работы с языковой моделью, не отвечает
за управление контекстом и не хранит данные Telegram-профиля (имя,
username, язык — будущие спринты, см. backlog_2.md §6/§7). Ноль
зависимостей от SQLAlchemy/Telegram/FastAPI — чистый Python, как и
`domain/conversation/value_objects.py`.

Инварианты (backlog_2.md §6, §7):
- `telegram_user_id` — положительное число (Telegram user id всегда > 0);
- `updated_at` не может быть раньше `created_at`;
- `telegram_user_id` не меняется после создания — обеспечивается
  неизменяемостью сущности (`frozen=True`): в Sprint 2 нет сценария,
  обновляющего `User`, поэтому отдельный метод изменения не нужен.

Ошибки — обычный `ValueError`, как в `value_objects.py`: отдельная
доменная ошибка пока не оправдана ни одним сценарием (claude.md §20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    """Пользователь системы — владелец всех принадлежащих ему диалогов."""

    id: UUID
    telegram_user_id: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.telegram_user_id <= 0:
            raise ValueError("telegram_user_id должен быть положительным числом")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at не может быть раньше created_at")
