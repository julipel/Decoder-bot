"""
`MemoryRepository` — абстрактный контракт доступа к долговременной памяти
пользователя (Sprint 5, задача S5-03, ADR-5.3/ADR-5.4/ADR-5.5/ADR-5.6).

Отдельный подпакет `application/memory/` (не `application/conversation/`)
— по тому же принципу, что и `application/profile/ports.py`:
`MemoryRecord`/долговременная память не входит в агрегат `conversation`
(ADR-2.3) и подключается к `ConversationRepositories` тем же приёмом, что
и `ProfileRepository` (ADR-3.3/ADR-5.5), не отдельной параллельной
фабрикой.

Стиль — как у `ProfileRepository`/`ConversationRepository`: `Protocol` +
`@runtime_checkable`, только доменные типы и типы стандартной библиотеки
в сигнатурах — ничего из SQLAlchemy.

`find_relevant` — единственный метод, реализующий бизнес-правило
«неподтверждённая память не входит в контекст» (§13.5 «Плана
реализации.md», ADR-5.6): фильтр `status = CONFIRMED` и исключение
истёкших записей применяются только здесь, не дублируются в use case'ах
памяти. Отдельный use-case класс `FindRelevantMemory` не создаётся —
`ProcessUserMessage` вызывает этот метод порта напрямую, тем же приёмом,
что уже применён к `ProfileRepository.get_active_profile` (ADR-5.4).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryStatus


@runtime_checkable
class MemoryRepository(Protocol):
    """
    `@runtime_checkable` — как у `ProfileRepository`/`ConversationRepository`:
    позволяет утверждать структурное соответствие fake-реализаций в
    тестах, не требуя наследования от протокола.
    """

    async def save(self, record: MemoryRecord) -> MemoryRecord:
        """Сохраняет НОВУЮ запись памяти и возвращает её (по аналогии с `MessageRepository.save`)."""
        ...

    async def find_relevant(self, user_id: UUID, limit: int) -> Sequence[MemoryRecord]:
        """
        Возвращает не более `limit` записей пользователя, релевантных
        текущему диалогу (ADR-5.6): только `status = CONFIRMED`, не
        истёкшие (`expires_at IS NULL OR expires_at > now`), отсортированные
        `confidence DESC, created_at DESC` — простой SQL, без векторного
        поиска. Единственная точка бизнес-правила «неподтверждённая
        память не входит в контекст» (§13.5 «Плана реализации.md»).
        Пустой список — штатный случай (нет подтверждённых записей), не
        исключение.
        """
        ...

    async def list_confirmed_by_user(self, user_id: UUID) -> Sequence[MemoryRecord]:
        """
        Возвращает ВСЕ подтверждённые (`status = CONFIRMED`) записи
        пользователя, без ограничения `limit` — для команды `/memory`
        (задача S5-07): пользователь должен видеть полный список своих
        фактов, не только те, что попадут в промпт следующего сообщения.
        """
        ...

    async def get_by_id(self, record_id: UUID) -> MemoryRecord | None:
        """Возвращает запись по `id` или `None`, если такой записи нет — штатный отрицательный исход, не исключение."""
        ...

    async def update_status(self, record_id: UUID, status: MemoryStatus, updated_by: str) -> MemoryRecord:
        """
        Атомарно меняет `status`/`updated_by`/`updated_at` записи и
        возвращает обновлённую запись — используется `ConfirmMemoryRecord`/
        `RejectMemoryRecord` (ADR-5.9). Запись должна существовать —
        вызывающий use case уже прочитал её через `get_by_id`.
        """
        ...

    async def delete(self, record_id: UUID, user_id: UUID) -> None:
        """
        Удаляет запись, только если она принадлежит `user_id` (ADR-5.10:
        «один пользователь не может удалить чужую запись», проверяется
        здесь, не только на уровне вызывающего Telegram-хендлера).
        Идемпотентна: удаление записи, которая уже не существует или
        принадлежит другому пользователю, не поднимает ошибку — реализация
        просто ничего не удаляет (0 затронутых строк — штатный исход).
        """
        ...
