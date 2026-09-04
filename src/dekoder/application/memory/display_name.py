"""
Общая логика факта «имя пользователя» — свободнотекстовая запись памяти
категории PERSONAL с префиксом NAME_FACT_PREFIX (изначально введена в
Sprint 13, `presentation/telegram/handlers/start.py`, для приветствия
по имени при повторном `/start`). Отдельного поля/схемы «имя
пользователя» в домене памяти по-прежнему нет и не оправдано
(claude.md §29, YAGNI) — та же свободнотекстовая модель, что и любой
другой факт `/remember`.

Вынесено из presentation в application, т.к. этот факт теперь читает
не только Telegram-хендлер (`/start`), но и `ProcessUserMessage`
(обращение к пользователю по имени в каждом ответе) — presentation не
может быть зависимостью application-слоя (claude.md §6), поэтому общий
код должен жить здесь, а не в `handlers/start.py`.
"""

from __future__ import annotations

from collections.abc import Sequence

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryCategory

NAME_FACT_PREFIX = "Обращение к пользователю: "


def format_display_name_fact(name: str) -> str:
    return f"{NAME_FACT_PREFIX}{name}"


def is_display_name_fact(record: MemoryRecord) -> bool:
    return record.category is MemoryCategory.PERSONAL and record.text.startswith(NAME_FACT_PREFIX)


def extract_display_name(records: Sequence[MemoryRecord]) -> str | None:
    for record in records:
        if is_display_name_fact(record):
            return record.text[len(NAME_FACT_PREFIX) :].strip()
    return None
