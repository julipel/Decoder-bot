"""
`ProfileStatus` (Sprint 3, задача S3-02, ADR-3.2) — статус строки каталога
профилей.

Только `ACTIVE`/`ARCHIVED` — в Sprint 3 нет ни одного use case,
переводящего профиль в `ARCHIVED` (это `DeactivateProfile`, Этап 10),
поэтому все сид-профили создаются сразу `ACTIVE`. Значения `CREATED` из
удалённого v2.0-скелета (`domain/profile/profile.py::ProfileStatus`,
S3-01) сознательно нет — оно было промежуточным статусом черновика
профиля, которого в модели Sprint 3 не существует.

`Enum`, не `str, Enum` — по стилю `domain/conversation/entities.py::
MessageRole`, не по стилю удалённого старого `ProfileStatus`.
"""

from __future__ import annotations

from enum import Enum


class ProfileStatus(Enum):
    """Статус профиля каталога. `ARCHIVED` не имеет вызывающего кода в Sprint 3 (задел на Этап 10)."""

    ACTIVE = "active"
    ARCHIVED = "archived"
