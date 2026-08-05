"""
Enum'ы доменной модели долговременной памяти (Sprint 5, задача S5-02,
ADR-5.3) — контролируемая память, заполняющая секцию 4 промпта
(`PromptContext.confirmed_memory_facts`, Sprint 4).

Значения — явная MVP-интерпретация §13.3/§13.4 «Плана реализации.md»
(они не называют конкретных значений), по прецеденту ADR-3.1.
`Enum`, не `str, Enum` — по стилю `domain/profile/value_objects.py::
ProfileStatus`.
"""

from __future__ import annotations

from enum import Enum


class MemoryCategory(Enum):
    """Категория факта — минимальный набор для фильтрации/группировки (ADR-5.3), расширяется по эксплуатации (YAGNI)."""

    PERSONAL = "personal"
    PREFERENCE = "preference"
    FACT = "fact"
    OTHER = "other"


class MemorySource(Enum):
    """
    Источник записи. `USER_EXPLICIT` — единственный достижимый в Sprint 5
    (через `/remember`). `ADMIN` зарезервирован для Этапа 10 (админ-
    интерфейс), `INFERRED` зарезервирован для гипотетического будущего
    сценария — автоматическое извлечение фактов AI прямо запрещено §13.2
    и ни один код-путь Sprint 5 значение `INFERRED` не производит.
    """

    USER_EXPLICIT = "user_explicit"
    ADMIN = "admin"
    INFERRED = "inferred"


class MemoryStatus(Enum):
    """
    Статус подтверждения записи. `/remember` создаёт запись сразу
    `CONFIRMED` (ADR-5.9) — `PENDING`/`REJECTED` реализованы полноценно
    (реальные ветки в `ConfirmMemoryRecord`/`RejectMemoryRecord`), но без
    вызывающего Telegram-сценария в Sprint 5.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MemoryConfidence(Enum):
    """Уровень значимости/подтверждения факта (§13.4/§13.8). `/remember` без явного указания создаёт `MEDIUM`."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
