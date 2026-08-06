"""
`ModelCatalogRepository` — абстрактный контракт доступа к статичному
каталогу AI-моделей (Sprint 7, задача S7-03, ADR-7.4). `ModelSelectionRepository`
— абстрактный контракт доступа к персональному выбору модели пользователем
(Sprint 7, задача S7-04, ADR-7.5).

`ModelCatalogRepository` — стиль как у `PromptTemplateRepository`
(`application/prompt/ports.py`): `Protocol`, синхронные методы (каталог
загружается в память один раз при построении конкретной реализации —
`infrastructure/model_catalog/config_repository.py::
ConfigModelCatalogRepository`, не на каждый вызов), только доменные типы и
типы стандартной библиотеки в сигнатурах — ничего из JSON/файловой
системы.

Не входит в `ConversationRepositories`/`ConversationRepositoriesFactory`
(`application/conversation/ports.py`) — у каталога моделей, как и у
`PromptTemplateRepository`, нет отношения к диалоговой транзакции (нет БД,
нет `AsyncSession`): внедряется в `ProcessUserMessage` отдельным
конструкторным параметром (S7-06), по образцу `KnowledgeSearchService`
(Sprint 6).

`ModelSelectionRepository` — стиль как у `MemoryRepository`/
`ProfileRepository`: `Protocol` + `@runtime_checkable`, асинхронные методы
(персональный выбор — реляционные данные за `AsyncSession`, ADR-7.5). В
отличие от `ModelCatalogRepository`, встроен в `ConversationRepositories`
как поле `model_selection` (`application/conversation/ports.py`) — тем же
приёмом, что `profiles`/`memory` (ADR-3.3/ADR-5.5), не отдельной
параллельной фабрикой.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel


@runtime_checkable
class ModelCatalogRepository(Protocol):
    """`@runtime_checkable` — как у `MemoryRepository`/`ProfileRepository`: позволяет проверять fake-реализации."""

    def get(self, model_id: ModelId) -> AIModel | None:
        """Возвращает модель каталога по `model_id` или `None`, если такой записи нет — штатный отрицательный исход."""
        ...

    def list_all(self) -> Sequence[AIModel]:
        """Возвращает все модели каталога — используется `ListAvailableModels`/Telegram-командой `/model`."""
        ...


@runtime_checkable
class ModelSelectionRepository(Protocol):
    """`@runtime_checkable` — как у `MemoryRepository`/`ProfileRepository`: позволяет проверять fake-реализации."""

    async def get_selected(self, user_id: UUID) -> ModelId | None:
        """
        Возвращает `model_id` персонального выбора пользователя или
        `None`, если выбор ещё не сделан — штатный отрицательный исход,
        не исключение (по аналогии с `ConversationRepository.get_by_id`).
        """
        ...

    async def select(self, user_id: UUID, model_id: ModelId) -> None:
        """
        Атомарно устанавливает персональный выбор модели пользователя —
        upsert по `user_id` (ADR-7.5): существующая запись обновляется,
        не дублируется, по прямому прецеденту `ProfileRepository.
        select_profile`/`user_active_profiles` (ADR-3.1).
        """
        ...
