"""
Доменные сущности `Conversation` (Aggregate Root) и `Message` (Sprint 2,
задача S2-02) — облегчённый DDD, без ORM/SQLAlchemy/Telegram-зависимостей
(backlog_2.md §6, ADR-2.3).

`Conversation` управляет собственным жизненным циклом (`close()`);
`Message` неизменяемо после создания и не может существовать вне
диалога — операции над сообщениями выполняются только через принадлежащий
им `Conversation` (backlog_2.md §6, «Границы агрегатов»). В Sprint 2 это
выражается тем, что `Message` не содержит операций, изменяющих его
состояние, а не полноценной агрегатной инфраструктурой (коллекций,
доменных событий и т.п.) — она сознательно не вводится (ADR-2.3).

Идентификаторы генерируются приложением (`uuid.UUID`) до сохранения —
сущности не полагаются на генерацию значений по умолчанию в БД.
Временные метки — timezone-aware UTC, назначаются вызывающим кодом
(Application Layer/mapper), сущности только проверяют согласованность
переданных значений.

Ошибки — обычный `ValueError`, как в `value_objects.py` и `domain/user/
entities.py`: отдельная доменная ошибка пока не оправдана (claude.md §20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class MessageRole(Enum):
    """Автор сообщения. Только `user`/`assistant` — Sprint 2 не хранит
    system/tool/function/developer-роли (backlog_2.md §7)."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class Message:
    """
    Единица взаимодействия внутри диалога — запрос пользователя либо
    ответ языковой модели.

    Неизменяема после создания (нет `updated_at`, нет методов изменения
    состояния) — соответствует инварианту backlog_2.md §6: «после
    сохранения содержимое сообщения не изменяется».
    """

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("content не может быть пустым или состоять только из пробелов")


@dataclass(slots=True)
class Conversation:
    """
    Отдельный диалог пользователя — Aggregate Root (ADR-2.3).

    Активен ⇔ `closed_at is None`. Единственный способ закрыть диалог —
    метод `close()`: он же обновляет `updated_at`, не допускает повторное
    закрытие и не допускает дату закрытия раньше `created_at`
    (backlog_2.md §6/§7). Владелец (`user_id`) не меняется — сознательно
    не предоставляется отдельный метод для его изменения.
    """

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at не может быть раньше created_at")
        if self.closed_at is not None and self.closed_at < self.created_at:
            raise ValueError("closed_at не может быть раньше created_at")

    @property
    def is_active(self) -> bool:
        """Диалог активен, пока не закрыт (`closed_at is None`)."""
        return self.closed_at is None

    def close(self, closed_at: datetime) -> None:
        """
        Закрывает диалог: устанавливает `closed_at`, обновляет `updated_at`.

        Повторное закрытие уже закрытого диалога запрещено (backlog_2.md
        §6: «закрытый диалог не может снова стать активным» — здесь же
        защищает и от повторного изменения `closed_at`). `closed_at` не
        может быть раньше `created_at`.
        """
        if self.closed_at is not None:
            raise ValueError("Conversation уже закрыт и не может быть закрыт повторно")
        if closed_at < self.created_at:
            raise ValueError("closed_at не может быть раньше created_at")
        self.closed_at = closed_at
        self.updated_at = closed_at
