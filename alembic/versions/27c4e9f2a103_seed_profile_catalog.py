"""seed profile catalog

Сид-миграция каталога профилей (задача S3-04, ADR-3.4): вносит 4
предустановленных профиля отдельной data migration поверх схемы,
созданной ревизией S3-03 (`14bf7e3ae815`).

Единственный механизм внесения данных — Alembic (`op.bulk_insert`), не
bootstrap-сидер: см. ADR-3.4, «Отклонённая альтернатива». UUID —
детерминированные константы, заданные прямо в этом файле, не `uuid4()`
— миграция воспроизводима при повторных прогонах на разных машинах/CI.
`downgrade()` удаляет ровно эти 4 строки по `id`, никогда не `DELETE
FROM profiles` без `WHERE`.

Состав каталога (текст черновой, согласован с пользователем как рабочий
вариант — backlog_3_tasks.md S3-04, «Черновой состав»; финальный
копирайтинг может быть уточнён отдельной миграцией после Sprint 3, см.
ADR-3.4 «Недостатки»):

- «Экспертный» — точно, структурированно, профессиональная терминология,
  явные риски/ограничения;
- «Дружелюбный» — тепло, простым языком, поддерживающий тон, примеры;
- «Деловой» (`is_default=True`) — кратко и по делу, формальный стиль,
  выводы в начале ответа; выбран дефолтом как наиболее близкий по духу
  к прежнему `_DEFAULT_SYSTEM_PROMPT` (`bootstrap/container.py`:
  «Отвечай кратко и по делу») — переход на Sprint 3 не меняет резко
  поведение ассистента для пользователей, ещё не выбравших профиль
  явно;
- «Креативный» — образные формулировки, метафоры, альтернативные точки
  зрения.

Все четыре строки: `status='active'`, `is_system=true`,
`forbidden_phrasing=[]`, `preferred_model=NULL`,
`response_length_hint=NULL`, `additional_constraints=''`. Ровно одна
строка `is_default=true` («Деловой») — обеспечивается и содержимым
данных, и частичным уникальным индексом `uq_profiles_is_default`
(S3-03) на уровне БД.

Revision ID: 27c4e9f2a103
Revises: 14bf7e3ae815
Create Date: 2026-08-03 17:05:00.000000

"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27c4e9f2a103"
down_revision: str | Sequence[str] | None = "14bf7e3ae815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Детерминированные UUID сид-профилей — константы, не uuid4() (ADR-3.4):
# миграция должна быть воспроизводима при повторных прогонах.
PROFILE_EXPERT_ID = UUID("8f14e45f-ceea-4c1c-b6df-2c3f1d0a0001")
PROFILE_FRIENDLY_ID = UUID("8f14e45f-ceea-4c1c-b6df-2c3f1d0a0002")
PROFILE_BUSINESS_ID = UUID("8f14e45f-ceea-4c1c-b6df-2c3f1d0a0003")
PROFILE_CREATIVE_ID = UUID("8f14e45f-ceea-4c1c-b6df-2c3f1d0a0004")

# Фиксированная временная метка сид-данных — naive UTC (та же дисциплона
# хранения, что и у mappers._to_naive_utc, S2-02/S3-03: SQLite не хранит
# offset, домен трактует naive-значение как UTC по соглашению).
_SEED_CREATED_AT = datetime(2026, 8, 3, 0, 0, 0)

_PROFILE_IDS = (PROFILE_EXPERT_ID, PROFILE_FRIENDLY_ID, PROFILE_BUSINESS_ID, PROFILE_CREATIVE_ID)


def _profiles_table() -> sa.Table:
    """Облегчённое табличное представление для `op.bulk_insert` — не импортирует ORM-модель Infrastructure Layer."""
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
    """Вставляет 4 сид-профиля каталога; ровно один с `is_default=True`."""
    op.bulk_insert(
        _profiles_table(),
        [
            {
                "id": PROFILE_EXPERT_ID,
                "name": "Экспертный",
                "description": (
                    "Профессиональный, точный стиль с явными ограничениями и терминологией предметной области."
                ),
                "system_instruction": (
                    "Отвечай точно, структурированно и по существу. Используй профессиональную "
                    "терминологию там, где это уместно. Явно указывай риски, допущения и "
                    "ограничения предложенного решения. Избегай общих фраз и «воды» — каждое "
                    "предложение должно нести содержательную информацию."
                ),
                "response_style": "точный, структурированный",
                "target_audience": "специалисты и профессионалы",
                "formality_level": "формальный",
                "preferred_structure": "выводы, риски и ограничения — явно, по пунктам",
                "forbidden_phrasing": [],
                "preferred_model": None,
                "response_length_hint": None,
                "additional_constraints": "",
                "status": "active",
                "is_system": True,
                "is_default": False,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            },
            {
                "id": PROFILE_FRIENDLY_ID,
                "name": "Дружелюбный",
                "description": "Тёплый, поддерживающий тон, простые слова, объяснение через понятные примеры.",
                "system_instruction": (
                    "Отвечай тепло и по-доброму, простым и понятным языком. Поддерживай "
                    "собеседника, избегай сложных терминов без объяснения. Используй понятные "
                    "примеры и аналогии из повседневной жизни, чтобы объяснить сложные вещи."
                ),
                "response_style": "тёплый, поддерживающий",
                "target_audience": "широкая аудитория, новички",
                "formality_level": "неформальный",
                "preferred_structure": "объяснение через примеры, без строгой структуры",
                "forbidden_phrasing": [],
                "preferred_model": None,
                "response_length_hint": None,
                "additional_constraints": "",
                "status": "active",
                "is_system": True,
                "is_default": False,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            },
            {
                "id": PROFILE_BUSINESS_ID,
                "name": "Деловой",
                "description": "Кратко и по делу, формальный деловой стиль, выводы и рекомендации в начале ответа.",
                "system_instruction": (
                    "Отвечай кратко и по делу, без лишних вступлений. Придерживайся делового, "
                    "формального стиля. Начинай ответ с главного вывода или рекомендации, затем "
                    "при необходимости добавляй краткое обоснование."
                ),
                "response_style": "деловой, лаконичный",
                "target_audience": "широкая аудитория",
                "formality_level": "формальный",
                "preferred_structure": "вывод/рекомендация в начале, затем краткое обоснование",
                "forbidden_phrasing": [],
                "preferred_model": None,
                "response_length_hint": None,
                "additional_constraints": "",
                "status": "active",
                "is_system": True,
                "is_default": True,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            },
            {
                "id": PROFILE_CREATIVE_ID,
                "name": "Креативный",
                "description": "Образные формулировки, метафоры, нестандартные идеи и альтернативные точки зрения.",
                "system_instruction": (
                    "Отвечай образно и нестандартно. Используй метафоры и яркие сравнения там, "
                    "где это уместно. Предлагай альтернативные точки зрения и нестандартные идеи, "
                    "не ограничиваясь очевидным решением."
                ),
                "response_style": "образный, нестандартный",
                "target_audience": "широкая аудитория, творческие задачи",
                "formality_level": "неформальный",
                "preferred_structure": "свободная форма, допускаются метафоры и примеры",
                "forbidden_phrasing": [],
                "preferred_model": None,
                "response_length_hint": None,
                "additional_constraints": "",
                "status": "active",
                "is_system": True,
                "is_default": False,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            },
        ],
    )


def downgrade() -> None:
    """Удаляет ровно эти 4 сид-строки по `id`, не трогая схему и никакие другие строки `profiles`."""
    profiles = _profiles_table()
    op.execute(profiles.delete().where(profiles.c.id.in_(_PROFILE_IDS)))
