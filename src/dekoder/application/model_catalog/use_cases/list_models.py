"""
ListAvailableModels — use case, возвращающий каталог AI-моделей вместе с
пометкой, какая из них активна для конкретного пользователя (Sprint 7,
задача S7-05, ADR-7.7).

Используется Telegram-хендлером `/model` (задача S7-07) для построения
inline-клавиатуры.

Композиция `ModelCatalogRepository.list_all()` (внедрён напрямую через
конструктор — по образцу `KnowledgeSearchService`, Sprint 6: каталог не
пользовательские, не транзакционные данные, не входит в
`ConversationRepositories`, ADR-7.4) + `repositories.model_selection.
get_selected(user.id)` (внутри короткой транзакции `ConversationRepositoriesFactory`,
ADR-7.5 — единственный способ добраться до персонального выбора).

Как и `ListMemoryRecords`/`GetActiveProfile`, пользователь НЕ создаётся
автоматически (`get_by_telegram_user_id`, не `get_or_create_...`) —
просмотр каталога не должен порождать пустую запись `User`: неизвестный
пользователь просто не имеет активной модели (`active_model_id=None`),
список моделей всё равно показывается.

Read-only операция — не журналируется (по аналогии с `ListMemoryRecords`).
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.model_catalog.dto import ListAvailableModelsCommand, ListAvailableModelsResult
from dekoder.application.model_catalog.ports import ModelCatalogRepository


class ListAvailableModels:
    def __init__(self, repositories: ConversationRepositoriesFactory, model_catalog: ModelCatalogRepository) -> None:
        self._repositories = repositories
        self._model_catalog = model_catalog

    async def execute(self, command: ListAvailableModelsCommand) -> ListAvailableModelsResult:
        models = tuple(self._model_catalog.list_all())

        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            active_model_id = None if user is None else await repositories.model_selection.get_selected(user.id)

        return ListAvailableModelsResult(models=models, active_model_id=active_model_id)
