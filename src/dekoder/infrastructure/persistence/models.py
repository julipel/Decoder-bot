"""
Единая точка импорта всех ORM-моделей Infrastructure Layer (задача S2-02).

Alembic autogenerate (`alembic/env.py`, `target_metadata = Base.metadata`)
обнаруживает таблицы только для тех ORM-классов, которые были
импортированы хотя бы один раз до сравнения схемы — декларативные классы
регистрируют себя в `Base.metadata` в момент определения класса. Этот
модуль импортируется из `alembic/env.py` и ни из какого другого места —
единственная причина его существования — гарантировать регистрацию всех
моделей для миграций, не заставляя `env.py` перечислять их по отдельности.
"""

from __future__ import annotations

from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.user_orm import UserORM

__all__ = ["ConversationORM", "MessageORM", "UserORM"]
