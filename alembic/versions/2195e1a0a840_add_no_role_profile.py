"""add no role profile

Data-миграция каталога профилей (внеспринтовая задача, 2026-09-09) — по
прямому запросу пользователя добавлен пятый профиль каталога «Без роли»:
прямой доступ к модели без ролевой персоны, поверх той же схемы `profiles`
(S3-03, `14bf7e3ae815`). Это НОВАЯ строка (`op.bulk_insert`), не апдейт
существующих 4 профилей — тот же приём вставки, что и в исходной
сид-миграции `27c4e9f2a103`, но без изменения её `id`-констант.

`system_instruction` не может быть пустым (`UserProfile.__post_init__`,
`domain/profile/entities.py`) — «без роли» реализовано как явная
инструкция «не придерживайся ролевой персоны», не как пустая строка.
Секция 1 Prompt Engine (базовая инструкция) и секция форматирования
ответа рендерятся безусловно для любого профиля (ADR-4.7) — этот профиль
не отключает их, только не добавляет собственную персону/стиль поверх.

`is_default=False` — существующий дефолт («Личный ассистент»,
PROFILE_BUSINESS_ID) не меняется; частичный уникальный индекс
`uq_profiles_is_default` не требует пересчёта. `is_system=True` — тот же
статус, что и у остальных 4 профилей каталога (общий, не персональный
каталог, ADR-3.1).

UUID — детерминированная константа (не `uuid4()`), тем же приёмом, что и
`27c4e9f2a103` — миграция воспроизводима при повторных прогонах.

Revision ID: 2195e1a0a840
Revises: fa08c9adb7c6
Create Date: 2026-09-09 13:05:00.000000

"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2195e1a0a840"
down_revision: str | Sequence[str] | None = "fa08c9adb7c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Тот же UUID-namespace, что и в 27c4e9f2a103 (8f14e45f-ceea-4c1c-b6df-2c3f1d0a000N) — следующий свободный слот.
PROFILE_NO_ROLE_ID = UUID("8f14e45f-ceea-4c1c-b6df-2c3f1d0a0005")

_MIGRATION_CREATED_AT = datetime(2026, 9, 9, 0, 0, 0)


def _profiles_table() -> sa.Table:
    """Тот же облегчённый табличный дескриптор, что и в 27c4e9f2a103 — не импортирует ORM Infrastructure Layer."""
    return sa.table(
        "profiles",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("system_instruction", sa.Text()),
        sa.column("response_style", sa.Text()),
        sa.column("target_audience", sa.Text()),
        sa.column("formality_level", sa.Text()),
        sa.column("preferred_structure", sa.Text()),
        sa.column("forbidden_phrasing", sa.JSON()),
        sa.column("preferred_model", sa.Text()),
        sa.column("response_length_hint", sa.Text()),
        sa.column("additional_constraints", sa.Text()),
        sa.column("status", sa.String(length=16)),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    """Вставляет пятый профиль каталога «Без роли» — прямой доступ к модели без ролевой персоны."""
    op.bulk_insert(
        _profiles_table(),
        [
            {
                "id": PROFILE_NO_ROLE_ID,
                "name": "Без роли",
                "description": (
                    "Прямой доступ к модели без ролевой персоны — только базовые правила общения и формата ответа."
                ),
                "system_instruction": (
                    "Не придерживайся никакой ролевой персоны, характера или сценария поведения. "
                    "Отвечай на вопросы пользователя напрямую, по существу, без дополнительного "
                    "стиля или образа сверх того, что уже задано базовыми правилами общения и "
                    "формата ответа."
                ),
                "response_style": "нейтральный, без персоны",
                "target_audience": "пользователи, которым не нужна ролевая персона",
                "formality_level": "нейтральный",
                "preferred_structure": "без специальных требований",
                "forbidden_phrasing": [],
                "preferred_model": None,
                "response_length_hint": None,
                "additional_constraints": "",
                "status": "active",
                "is_system": True,
                "is_default": False,
                "created_at": _MIGRATION_CREATED_AT,
                "updated_at": _MIGRATION_CREATED_AT,
            },
        ],
    )


def downgrade() -> None:
    """Удаляет ровно эту одну строку по `id`, не трогая остальные 4 профиля каталога."""
    profiles = _profiles_table()
    op.execute(profiles.delete().where(profiles.c.id == PROFILE_NO_ROLE_ID))
