"""
DTO прикладного слоя памяти (Sprint 5, задача S5-05) — вход/выход
use case'ов `CreateMemoryRecord`/`ConfirmMemoryRecord`/`RejectMemoryRecord`/
`ListMemoryRecords`/`DeleteMemoryRecord`.

Тот же стиль, что и `application/profile/dto.py`: обычные
`dataclass(frozen=True)`, без Pydantic и без привязки к Telegram SDK —
внутренний контракт application-слоя.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)


@dataclass(frozen=True)
class CreateMemoryRecordCommand:
    """
    `status`/`source` — обязательные параметры без значения по умолчанию
    (ADR-5.9): `CreateMemoryRecordUseCase` не хардкодит `status=CONFIRMED`
    внутри себя — Telegram-хендлер `/remember` (задача S5-07) передаёт
    `status=CONFIRMED, source=USER_EXPLICIT` явно.

    `category` по умолчанию `OTHER` — `/remember` не даёт пользователю
    выбрать категорию, `confidence` по умолчанию `MEDIUM` (ADR-5.3: «/remember
    без явного указания создаёт MEDIUM»), `is_sensitive` по умолчанию
    `False`.
    """

    telegram_user_id: int
    text: str
    status: MemoryStatus
    source: MemorySource
    category: MemoryCategory = MemoryCategory.OTHER
    confidence: MemoryConfidence = MemoryConfidence.MEDIUM
    is_sensitive: bool = False
    expires_at: datetime | None = None


@dataclass(frozen=True)
class CreateMemoryRecordResult:
    """
    `record` не `None` — в отличие от `ClearConversation`/`StartNewConversation`,
    пользователь создаётся автоматически (`get_or_create_by_telegram_user_id`,
    по аналогии с `ProcessUserMessage`): `/remember` может быть первым
    действием пользователя, сохранение факта не должно молча завершаться
    без эффекта только потому, что пользователь ещё не отправил `/start`.
    """

    record: MemoryRecord


@dataclass(frozen=True)
class ConfirmMemoryRecordCommand:
    """Не привязан к `telegram_user_id` — задел на будущий сценарий подтверждения (админка/ИИ-предложения, ADR-5.9)."""

    record_id: UUID
    updated_by: str


@dataclass(frozen=True)
class ConfirmMemoryRecordResult:
    """`record is None`, если `record_id` неизвестен — штатный отрицательный исход, не исключение."""

    record: MemoryRecord | None


@dataclass(frozen=True)
class RejectMemoryRecordCommand:
    record_id: UUID
    updated_by: str


@dataclass(frozen=True)
class RejectMemoryRecordResult:
    """`record is None`, если `record_id` неизвестен — штатный отрицательный исход, не исключение."""

    record: MemoryRecord | None


@dataclass(frozen=True)
class ListMemoryRecordsCommand:
    telegram_user_id: int


@dataclass(frozen=True)
class ListMemoryRecordsResult:
    """Только `CONFIRMED`-записи (`MemoryRepository.list_confirmed_by_user`) — для команды `/memory`."""

    records: tuple[MemoryRecord, ...]


@dataclass(frozen=True)
class DeleteMemoryRecordCommand:
    telegram_user_id: int
    record_id: UUID
