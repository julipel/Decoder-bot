"""
`LLMProvider` — абстрактный контракт вызова генеративной модели,
`ConversationRepository` — абстрактный контракт доступа к диалогам
(Sprint 2, задача S2-04), `MessageRepository` — абстрактный контракт
доступа к сообщениям диалога (Sprint 2, задача S2-05), и
`ConversationRepositories`/`ConversationRepositoriesFactory` — контракт
получения короткоживущей группы из всех трёх репозиториев для одной
транзакции (Sprint 2, задача S2-06, см. ниже).

`application/conversation/` не импортирует OpenRouter (или любого другого
конкретного провайдера) — только этот протокол. Конкретные реализации
(например, адаптер OpenRouter) живут в `infrastructure/` и подключаются
через composition root, как и остальные порты проекта.

Только `generate()` — `healthcheck()` не добавлен, т.к. сейчас нет
use case'а, который бы его вызывал (см. задачу: не создавать
неиспользуемые методы).

`ConversationRepository`/`MessageRepository` живут здесь, а не в отдельном
`application/conversation/` подпакете (которого и так уже нет — он и есть
текущий пакет) — в отличие от `UserRepository` (`application/user/
ports.py`), `Conversation`/`Message` — часть агрегата `conversation`
(ADR-2.3, backlog_2.md §6 «Границы агрегатов»), поэтому их порты
размещаются рядом с `LLMProvider` в том же пакете, что и доменные сущности
(`domain/conversation/entities.py`). Стиль — тот же: `Protocol` +
`@runtime_checkable`, только доменные типы и типы стандартной библиотеки в
сигнатурах (backlog_2.md §8, «Доменные и инфраструктурные типы»; §15,
инварианты 3/4/12).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.user.ports import UserRepository
from dekoder.domain.conversation.entities import Conversation, Message


@runtime_checkable
class LLMProvider(Protocol):
    """
    `@runtime_checkable` включает `isinstance(obj, LLMProvider)` — только
    проверка наличия метода нужной формы, не сигнатуры типов, но этого
    достаточно, чтобы в тестах утверждать «fake-объект соответствует порту»,
    не наследуясь от него явно.
    """

    async def generate(self, request: LLMRequest) -> LLMResponse: ...


@runtime_checkable
class ConversationRepository(Protocol):
    """
    `@runtime_checkable` — как у `LLMProvider`/`UserRepository`: позволяет
    утверждать структурное соответствие fake-реализаций в тестах, не
    требуя наследования от протокола.

    Активность диалога определяется строго через `closed_at is None`
    (`Conversation.is_active`, `domain/conversation/entities.py`) —
    отдельного статуса/поля не существует (backlog_2.md §7).

    Отсутствие записи — нормальное состояние, не исключение:
    `get_by_id`/`get_active_by_user_id` возвращают `Conversation | None`
    (backlog_2.md §8, «Обработка отсутствующих данных»); отсутствие
    активного диалога — штатная ситуация, приводящая к созданию нового
    через `get_or_create_active`, а не к ошибке.

    `ConversationRepository` не проверяет существование пользователя и не
    вызывает `UserRepository` — эту гарантию даёт внешний ключ
    `conversations.user_id → users.id` на уровне БД (S2-02); получить
    или создать `User` до вызова этого репозитория — ответственность
    вызывающего Use Case (backlog_2.md §8, «UserRepository» /
    «ConversationRepository», разделение ответственности).
    """

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None: ...

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        """
        Возвращает активный диалог пользователя (`closed_at is None`) или
        `None`, если такого нет. Закрытые диалоги никогда не
        возвращаются как активные.
        """
        ...

    async def save(self, conversation: Conversation) -> Conversation:
        """
        Сохраняет НОВЫЙ диалог. Попытка сохранить второй активный диалог
        того же пользователя должна быть отклонена базой данных
        (частичный уникальный индекс `uq_conversations_active_user`,
        S2-02) — реализация не должна скрывать это нарушение.
        """
        ...

    async def close(self, conversation: Conversation) -> Conversation:
        """
        Закрывает диалог. Ожидает сущность, уже переведённую в закрытое
        состояние доменным методом `Conversation.close(...)` — проверка
        доменных инвариантов (нельзя закрыть уже закрытый диалог, нельзя
        закрыть раньше `created_at`) выполняется в Domain Layer, не
        здесь. Реализация обновляет только `closed_at`/`updated_at`
        конкретной записи, не удаляет диалог и не трогает сообщения.
        """
        ...

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        """
        Идемпотентная операция: находит активный диалог пользователя и
        возвращает его; если активного диалога нет — создаёт новый
        (`closed_at=None`) и сохраняет. Как и у `UserRepository.
        get_or_create_by_telegram_user_id`, единственный источник истины
        против дублей активного диалога — уникальное ограничение БД
        (`uq_conversations_active_user`, S2-02), не проверка «сначала
        SELECT, затем INSERT» на уровне Python (backlog_2.md §8,
        «Конкурентный доступ»).
        """
        ...


@runtime_checkable
class MessageRepository(Protocol):
    """
    `@runtime_checkable` — как у `LLMProvider`/`ConversationRepository`:
    позволяет утверждать структурное соответствие fake-реализаций в
    тестах, не требуя наследования от протокола.

    `MessageRepository` не решает роль сообщения, не создаёт диалог и не
    создаёт пользователя — эти данные передаёт вызывающий Use Case
    (backlog_2.md §8, «MessageRepository», «Сохранение сообщений»).
    Репозиторий не вызывает `ConversationRepository`/`UserRepository` и не
    проверяет существование диалога сам — эту гарантию даёт внешний ключ
    `messages.conversation_id → conversations.id` на уровне БД (S2-02), по
    аналогии с тем, как `ConversationRepository` полагается на FK
    `conversations.user_id → users.id`, а не на собственную проверку.
    """

    async def save(self, message: Message) -> Message:
        """
        Сохраняет НОВОЕ сообщение. Сообщения неизменяемы (backlog_2.md §6:
        «после сохранения содержимое сообщения не изменяется») — отдельного
        `update()`/`edit()` не существует и не появится. Повторное
        сохранение с уже использованным `id` должно быть отклонено базой
        данных через первичный ключ, реализация не должна скрывать это
        нарушение. Сохраняет исходные `id`/`role`/`content`/`created_at`
        без изменений.
        """
        ...

    async def history(self, conversation_id: UUID) -> list[Message]:
        """
        Возвращает все сообщения одного диалога в детерминированном
        хронологическом порядке `created_at ASC, id ASC` — вторичная
        сортировка по `id` обязательна для детерминизма при совпадающих
        `created_at` (backlog_2.md §7, «Порядок сообщений»). Пустая
        история — пустой список, не исключение и не `None`. Фильтр строго
        по `conversation_id` — сообщения других диалогов никогда не
        попадают в результат.
        """
        ...

    async def clear(self, conversation_id: UUID) -> int:
        """
        Удаляет ВСЕ сообщения диалога одной операцией удаления (не
        построчно, не через ORM-каскад) и возвращает количество удалённых
        строк. Не удаляет сам `Conversation`, не изменяет `closed_at`, не
        создаёт новый диалог (backlog_2.md §7, «Правила удаления»; §8,
        «Очистка истории»). Идемпотентна: повторный вызов на уже пустой
        истории возвращает `0`, не является ошибкой.
        """
        ...


@dataclass(frozen=True)
class ConversationRepositories:
    """
    Группа из трёх репозиториев, нужных `ProcessUserMessage` внутри ОДНОЙ
    короткоживущей транзакции (Sprint 2, задача S2-06).

    Это не Generic Repository и не самостоятельный Unit of Work —
    абстрактный Unit of Work из backlog_2.md §15 (инвариант 14) явно
    запрещён; `ConversationRepositories` не предоставляет
    `begin()`/`commit()`/`rollback()` и вообще не знает про транзакции —
    просто именованный набор из уже готовых `UserRepository`/
    `ConversationRepository`/`MessageRepository`, каждый из которых
    остаётся тем же протоколом, что и раньше. Транзакционные границы
    (когда открыть/закрыть сессию, когда закоммитить) остаются
    инфраструктурной ответственностью `session_scope()`
    (`infrastructure/persistence/session.py`, задача S2-01) — `bootstrap/
    repositories.py` оборачивает его в `ConversationRepositoriesFactory`
    ниже.
    """

    users: UserRepository
    conversations: ConversationRepository
    messages: MessageRepository


ConversationRepositoriesFactory = Callable[[], AbstractAsyncContextManager[ConversationRepositories]]
"""
Фабрика короткоживущих транзакций для `ProcessUserMessage` (Sprint 2,
задача S2-06).

Вызов `repositories_factory()` возвращает асинхронный контекстный
менеджер: вход в `async with` открывает новую независимую транзакцию
(в инфраструктурной реализации — `session_scope()` поверх новой
`AsyncSession`) и отдаёт `ConversationRepositories`, построенные над ней;
успешный выход из блока коммитит транзакцию, исключение внутри блока —
откатывает. Каждый вызов `repositories_factory()` — новая, независимая
транзакция (backlog_2.md §9, «Транзакционные границы»: «короткие
транзакции», не одна долгая на весь сценарий).

Это единственный способ, которым `ProcessUserMessage` получает доступ к
хранилищу — сам он не импортирует SQLAlchemy, `AsyncSession` или
`async_sessionmaker` (`application/conversation/use_cases/
process_user_message.py`, claude.md §6/§24, backlog_2.md §15, инварианты
3/4). Конкретная реализация (`bootstrap/repositories.py::
build_conversation_repositories_factory`) — единственное место, которому
разрешено знать одновременно про этот тип и про `AsyncSession`/
`session_scope()` — то же правило единственной точки сборки, что и у
остальных bootstrap-фабрик (claude.md §8.5).
"""
