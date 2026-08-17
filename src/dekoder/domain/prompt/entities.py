"""
Доменная сущность `PromptTemplate` (Sprint 4, задача S4-02, ADR-4.2/ADR-4.3) —
одна запись файлового каталога шаблонов Prompt Engine (`backlog_4.md` §5,
манифест на файл в `infrastructure/prompts/templates/`).

Один плоский `frozen`-датакласс, по стилю `domain/profile/entities.py::
UserProfile` — без обёрток `PromptTemplateId`/`PromptVersion` сверх того,
что явно требуется: версионирование идёт по `version` (произвольная
строка контента), не по `id` (устойчивый идентификатор шаблона, стабилен
между версиями текста).

`PromptTemplateStatus` — `Enum` (не `str, Enum`), по прецеденту
`domain/profile/value_objects.py::ProfileStatus`/`domain/conversation/
entities.py::MessageRole`. `ARCHIVED` не имеет вызывающей логики в
Sprint 4 (все шесть сид-шаблонов — `ACTIVE`) — задел на будущее, по
аналогии с `ProfileStatus.ARCHIVED` (ADR-3.2).

Ноль зависимостей от SQLAlchemy/Alembic/Telegram/HTTP — чистый Python,
как остальной `domain/`. Ошибки — обычный `ValueError` (claude.md §20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PromptTemplateStatus(Enum):
    """Статус записи каталога шаблонов. `ARCHIVED` не имеет вызывающего кода в Sprint 4 (задел на будущее)."""

    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """
    Одна запись файлового каталога шаблонов (`backlog_4.md` §5).

    `id` — устойчивый идентификатор, стабильный между версиями текста
    (совпадает с `purpose` для сид-шаблонов Sprint 4 — ровно один шаблон
    на секцию, ADR-4.3). `text` — тело шаблона (`string.Template`-синтаксис,
    ADR-4.2) как оно прочитано из файла, без подстановки переменных.
    `required_variables` — список имён `$variable`, обязательных к
    подстановке перед `.substitute()` (проверяется в `application/prompt/
    services/prompt_builder.py`, не здесь — ADR-4.2/4.9).
    """

    id: str
    name: str
    version: str
    purpose: str
    text: str
    required_variables: tuple[str, ...]
    status: PromptTemplateStatus
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id не может быть пустым")
        if not self.name.strip():
            raise ValueError("name не может быть пустым")
        if not self.version.strip():
            raise ValueError("version не может быть пустым")
        if not self.purpose.strip():
            raise ValueError("purpose не может быть пустым")
        if not self.text.strip():
            raise ValueError("text не может быть пустым")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at должен быть timezone-aware")
