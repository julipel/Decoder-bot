"""
SelectModel — use case, устанавливающий персональный выбор AI-модели
пользователем (Sprint 7, задача S7-05, ADR-7.7/ADR-7.9).

Используется callback-хендлером выбора модели `/model` (задача S7-07) —
единственная операция записи каталога моделей во всём Sprint 7.

Отклоняет попытку выбрать модель, отсутствующую в каталоге, или модель с
`availability = UNAVAILABLE` — явной доменной ошибкой (`ApplicationError`
с конкретным `code`, не молчаливый no-op и не тихо игнорируемый статус,
backlog_7_tasks.md S7-05): `ModelSelectionRepository.select(...)` не
вызывается в обоих случаях. Это единственная точка, где отклоняется
попытка выбрать `UNAVAILABLE`/несуществующую модель (ADR-7.9) — не
полагается на то, что Telegram UI не покажет такую кнопку (тот же
принцип, что проверка владения записью в `DeleteMemoryRecord`, ADR-5.10).

Как и `CreateMemoryRecord` (не как `GetActiveProfile`/`SelectProfile`),
пользователь создаётся автоматически (`get_or_create_by_telegram_user_id`)
— выбор модели должен быть возможен независимо от того, писал ли
пользователь что-то раньше, и в отличие от read-only `ListAvailableModels`/
`GetSelectedModel` здесь запись в `user_active_models` требует реального
`user_id` (внешний ключ на `users.id`).

`ValidateModelAvailability` из §15.4 не выделяется в отдельный use-case
класс (ADR-7.7) — проверка `AIModel.availability` инкапсулирована прямо
здесь.

Логирует успешный выбор через `shared.logging` (по аналогии с прочими
операциями записи каталога/памяти, ADR-5.12) — `model_id` не является
чувствительными данными, логируется без ограничений.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.model_catalog.dto import SelectModelCommand, SelectModelResult
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.shared.errors import ApplicationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class SelectModel:
    def __init__(self, repositories: ConversationRepositoriesFactory, model_catalog: ModelCatalogRepository) -> None:
        self._repositories = repositories
        self._model_catalog = model_catalog

    async def execute(self, command: SelectModelCommand) -> SelectModelResult:
        model = self._model_catalog.get(command.model_id)
        if model is None:
            raise ApplicationError(
                message=f"Попытка выбрать неизвестную модель каталога: {command.model_id.value}",
                user_message="Эта модель больше недоступна. Отправьте /model, чтобы увидеть актуальный список.",
                code="MODEL_NOT_FOUND",
                metadata={"model_id": command.model_id.value},
            )
        if model.availability is ModelAvailability.UNAVAILABLE:
            raise ApplicationError(
                message=f"Попытка выбрать недоступную модель каталога: {command.model_id.value}",
                user_message="Эта модель сейчас недоступна для выбора. Отправьте /model, чтобы выбрать другую.",
                code="MODEL_UNAVAILABLE",
                metadata={"model_id": command.model_id.value},
            )

        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(command.telegram_user_id)
            await repositories.model_selection.select(user.id, command.model_id)
            _logger.info("model_selected", user_id=str(user.id), model_id=command.model_id.value)

        return SelectModelResult(model=model)
