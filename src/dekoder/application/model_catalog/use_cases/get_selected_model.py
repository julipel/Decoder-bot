"""
GetSelectedModel — use case, возвращающий текущий персональный выбор
модели пользователя, разрешённый через каталог (Sprint 7, задача S7-05,
ADR-7.7).

Используется ТОЛЬКО Telegram-хендлером `/model` (задача S7-07) для
отображения текущего выбора — не `ProcessUserMessage` (тот обращается к
`repositories.model_selection`/`ModelCatalogRepository` напрямую, тем же
приёмом, что и `get_active_profile`, ADR-7.7 «GetSelectedModel... но
вызывается только Telegram-хендлером /model»).

`result.model is None`, если пользователь неизвестен, персональный выбор
не сделан, ИЛИ выбор указывает на `model_id`, которого больше нет в
текущем каталоге (устойчивость к изменению каталога после того, как
выбор был сделан — DoD ADR-7.7/S7-05 AC-3) — три штатных, неразличаемых
для вызывающего кода отрицательных исхода, не исключения.

Read-only операция — не журналируется.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.model_catalog.dto import GetSelectedModelCommand, GetSelectedModelResult
from dekoder.application.model_catalog.ports import ModelCatalogRepository


class GetSelectedModel:
    def __init__(self, repositories: ConversationRepositoriesFactory, model_catalog: ModelCatalogRepository) -> None:
        self._repositories = repositories
        self._model_catalog = model_catalog

    async def execute(self, command: GetSelectedModelCommand) -> GetSelectedModelResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return GetSelectedModelResult(model=None)

            selected_model_id = await repositories.model_selection.get_selected(user.id)

        if selected_model_id is None:
            return GetSelectedModelResult(model=None)

        return GetSelectedModelResult(model=self._model_catalog.get(selected_model_id))
