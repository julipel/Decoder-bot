"""
`ProfileRepository` — абстрактный контракт доступа к каталогу профилей и
активному выбору пользователя (Sprint 3, задача S3-05, ADR-3.1/ADR-3.3).

Отдельный подпакет `application/profile/` (не `application/conversation/`,
где живёт `LLMProvider`/`ConversationRepository`) — по тому же принципу,
что и `application/user/ports.py`: `UserProfile`/каталог профилей не
входят в агрегат `conversation` (ADR-2.3) и не принадлежат ни одному
конкретному пользователю в Sprint 3 (общий сид-каталог, backlog_3.md §1).

Стиль — как у `UserRepository`/`ConversationRepository`: `Protocol` +
`@runtime_checkable`, только доменные типы и типы стандартной библиотеки
в сигнатурах — ничего из SQLAlchemy.

В Sprint 3 нет операций записи каталога (`create`/`update`/`archive`) —
единственная операция записи, `select_profile`, изменяет только связь
«пользователь → активный профиль», не сам профиль (backlog_3.md §3,
«Ограничения объёма CRUD»).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.domain.profile.entities import UserProfile


@runtime_checkable
class ProfileRepository(Protocol):
    """
    `@runtime_checkable` — как у `UserRepository`/`ConversationRepository`:
    позволяет утверждать структурное соответствие fake-реализаций в
    тестах, не требуя наследования от протокола.
    """

    async def list_active(self) -> list[UserProfile]:
        """Возвращает все профили каталога со `status == ProfileStatus.ACTIVE`."""
        ...

    async def get_active_profile(self, user_id: UUID) -> UserProfile:
        """
        Возвращает активный профиль пользователя: явно выбранный
        (`user_active_profiles`), если выбор есть, иначе профиль с
        `is_default=True` (ADR-3.1). Не возвращает `None` в штатном
        случае — отсутствие каталога после сид-миграции S3-04 не
        должно происходить, но реализация не должна падать молча, если
        это всё же так (см. `infrastructure/persistence/
        profile_repository.py`).
        """
        ...

    async def select_profile(self, user_id: UUID, profile_id: UUID) -> UserProfile | None:
        """
        Атомарно устанавливает активный профиль пользователя (upsert
        `user_active_profiles`, ADR-3.1). Возвращает выбранный профиль
        при успехе; возвращает `None`, если `profile_id` не существует
        или не `ACTIVE` — штатный отрицательный исход, не исключение
        (по аналогии с `ConversationRepository.get_by_id`, возвращающим
        `None` для «нет записи»). Текущий выбор пользователя не
        изменяется, если `profile_id` неизвестен/неактивен.
        """
        ...
