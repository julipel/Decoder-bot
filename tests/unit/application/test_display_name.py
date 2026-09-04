"""
Тесты `application/memory/display_name.py` — общей логики факта «имя
пользователя», переиспользуемой `handlers/start.py` (presentation) и
`ProcessUserMessage` (application).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from dekoder.application.memory.display_name import (
    NAME_FACT_PREFIX,
    extract_display_name,
    format_display_name_fact,
    is_display_name_fact,
)
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)


def _make_record(**overrides: object) -> MemoryRecord:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "text": "Работает Python-разработчиком.",
        "category": MemoryCategory.FACT,
        "source": MemorySource.USER_EXPLICIT,
        "status": MemoryStatus.CONFIRMED,
        "confidence": MemoryConfidence.MEDIUM,
        "is_sensitive": False,
        "expires_at": None,
        "updated_by": "user",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryRecord(**defaults)  # type: ignore[arg-type]


def test_format_display_name_fact_uses_stable_prefix() -> None:
    assert format_display_name_fact("Алекс") == f"{NAME_FACT_PREFIX}Алекс"


def test_is_display_name_fact_requires_personal_category_and_prefix() -> None:
    name_record = _make_record(text=format_display_name_fact("Алекс"), category=MemoryCategory.PERSONAL)
    wrong_category = _make_record(text=format_display_name_fact("Алекс"), category=MemoryCategory.FACT)
    wrong_prefix = _make_record(text="Алекс", category=MemoryCategory.PERSONAL)

    assert is_display_name_fact(name_record) is True
    assert is_display_name_fact(wrong_category) is False
    assert is_display_name_fact(wrong_prefix) is False


def test_extract_display_name_finds_the_name_among_other_facts() -> None:
    other_fact = _make_record(text="Живёт в Берлине.")
    name_record = _make_record(text=format_display_name_fact("Алекс"), category=MemoryCategory.PERSONAL)

    assert extract_display_name([other_fact, name_record]) == "Алекс"


def test_extract_display_name_returns_none_when_no_name_fact_present() -> None:
    other_fact = _make_record(text="Живёт в Берлине.")

    assert extract_display_name([other_fact]) is None
