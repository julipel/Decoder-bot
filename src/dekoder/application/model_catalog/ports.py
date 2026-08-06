"""
`ModelCatalogRepository` — абстрактный контракт доступа к статичному
каталогу AI-моделей (Sprint 7, задача S7-03, ADR-7.4).

Стиль — как у `PromptTemplateRepository` (`application/prompt/ports.py`):
`Protocol`, синхронные методы (каталог загружается в память один раз при
построении конкретной реализации — `infrastructure/model_catalog/
config_repository.py::ConfigModelCatalogRepository`, не на каждый вызов),
только доменные типы и типы стандартной библиотеки в сигнатурах — ничего
из JSON/файловой системы.

Не входит в `ConversationRepositories`/`ConversationRepositoriesFactory`
(`application/conversation/ports.py`) — у каталога моделей, как и у
`PromptTemplateRepository`, нет отношения к диалоговой транзакции (нет БД,
нет `AsyncSession`): внедряется в `ProcessUserMessage` отдельным
конструкторным параметром (S7-06), по образцу `KnowledgeSearchService`
(Sprint 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

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
