"""
UserRepository — абстрактный контракт доступа к пользователям (Sprint 2,
задача S2-03).

Отдельный подпакет `application/user/` (не `application/conversation/`,
где живёт `LLMProvider`) — по аналогии с тем, куда S2-02 положил
доменную сущность (`domain/user/entities.py`, не `domain/conversation/`):
`User` не входит в агрегат `Conversation` (ADR-2.3, backlog_2.md §6
«Границы агрегатов»), поэтому и его порт живёт рядом со своим доменом,
а не внутри `application/conversation/ports.py`.

Стиль — как у `LLMProvider` (`application/conversation/ports.py`):
`Protocol` + `@runtime_checkable`, только доменные типы и типы стандартной
библиотеки в сигнатурах — ничего из SQLAlchemy (backlog_2.md §8,
«Доменные и инфраструктурные типы»; §15, инварианты 3/4/12).

`UserRepository` не хранит Telegram-профиль пользователя, не управляет
диалогами и не создаёт активный диалог — это ответственность
`ConversationRepository` (следующая задача Sprint 2, backlog_2.md §8).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.domain.user.entities import User


@runtime_checkable
class UserRepository(Protocol):
    """
    `@runtime_checkable` — как у `LLMProvider`: позволяет утверждать
    структурное соответствие fake-реализаций в тестах, не требуя
    наследования от протокола.

    Отсутствие записи — нормальное состояние, не исключение:
    `get_by_id`/`get_by_telegram_user_id` возвращают `User | None`
    (backlog_2.md §8, «Обработка отсутствующих данных»).

    `save()` сохраняет НОВУЮ сущность. Отдельного `update()` в контракте
    нет: `User` в Sprint 2 не имеет изменяемых полей бизнес-смысла
    (Telegram-профиль, настройки — будущие спринты) — сущность
    неизменяема на уровне домена (`domain/user/entities.py`,
    `frozen=True`), поэтому сценария «изменить уже сохранённого
    пользователя» пока не существует.
    """

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None: ...

    async def save(self, user: User) -> User: ...

    async def get_or_create_by_telegram_user_id(self, telegram_user_id: int) -> User:
        """
        Идемпотентная операция: повторный вызов с тем же
        `telegram_user_id` возвращает пользователя с тем же внутренним
        `id` — как при первом, так и при последующих вызовах, в том числе
        при конкурентных вызовах для одного и того же `telegram_user_id`
        (backlog_2.md §8, «Конкурентный доступ»). Единственный источник
        истины против дублей — уникальное ограничение базы данных на
        `telegram_user_id` (`uq_users_telegram_user_id`, задача S2-02), а
        не проверка вида «сначала SELECT, затем INSERT» на уровне Python.
        """
        ...
