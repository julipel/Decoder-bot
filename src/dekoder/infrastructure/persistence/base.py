"""
Единая декларативная база SQLAlchemy (задача S2-01 — только инфраструктура).

`Base` — единственный общий predok для всех будущих ORM-моделей
(`User`, `Conversation`, `Message` появятся в следующих задачах Sprint 2,
не в этой). Единая база нужна, чтобы у Alembic был один `MetaData`
объект для autogenerate (`Base.metadata`, см. `alembic/env.py`).

ORM-модели, унаследованные от `Base`, — деталь Infrastructure Layer и не
импортируются из Domain или Application Layer (backlog_2.md §5, §15,
инвариант 3/12; claude.md §6/§24).

`Base.metadata.create_all()` не вызывается нигде в рабочем коде — схема
базы данных создаётся исключительно через Alembic-миграции (кроме
тестового окружения, см. backlog_2.md §5).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общая typed-declarative база для ORM-моделей Infrastructure Layer."""
