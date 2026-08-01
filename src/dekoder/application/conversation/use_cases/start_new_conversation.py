"""
StartNewConversation — use case, завершающий текущий активный диалог
пользователя и создающий новый пустой диалог (Sprint 2, задача S2-07).

Используется обработчиком команды `/new` — подключение к Telegram Adapter
является отдельной, следующей задачей Sprint 2 (S2-08); здесь Telegram
SDK не задействован вовсе.

Зависит от `ConversationRepositoriesFactory` (`application/conversation/
ports.py`) — того же порта, каким `ProcessUserMessage` (задача S2-06)
получает короткоживущую транзакцию с группой репозиториев. Переиспользование
существующей фабрики, а не введение отдельного, более узкого порта —
осознанный выбор: `ConversationRepositoriesFactory` уже является
утверждённой (backlog_2.md §15, инвариант 14 запрещает вводить Unit of
Work или новые абстракции хранения «на будущее») точкой получения
`UserRepository`+`ConversationRepository` в одной атомарной транзакции, а
добавление параллельного порта с тем же смыслом было бы избыточной
абстракцией. `repositories.messages` (тот же объект, что и
`MessageRepository`) НИ РАЗУ не вызывается ни в одном методе этого файла —
задача S2-07 прямо запрещает use case'у работать с историей сообщений
(«не удаляет сообщения предыдущего диалога», «не работает с
MessageRepository», backlog_2_tasks.md S2-07).

Не зависит от SQLAlchemy, ORM-моделей, Telegram SDK и `LLMProvider` — ни
один из них не импортируется в этом файле. В отличие от
`ProcessUserMessage`, пользователь НЕ создаётся автоматически: если
`UserRepository.get_by_telegram_user_id()` возвращает `None`, use case
завершается успешно (`StartNewConversationResult(conversation_id=None)`),
не создавая ни пользователя, ни диалог (backlog_2_tasks.md S2-07: «Если
пользователь отсутствует — вернуть успешный результат без ошибок»).

Закрытие текущего активного диалога и создание нового выполняются в ОДНОЙ
короткой транзакции (один вызов `self._repositories()`), а не в двух
раздельных, как транзакции 1/2/3 в `ProcessUserMessage`: там разделение
было обязательным, чтобы не удерживать транзакцию БД во время сетевого
вызова `LLMProvider.generate()` (backlog_2.md §9); здесь сетевых вызовов
нет вовсе, поэтому закрытие старого и сохранение нового диалога — единая
атомарная операция, которая или применяется целиком, или полностью
откатывается при ошибке (не оставляет пользователя без активного диалога
из-за сбоя между двумя шагами).

`process_user_message.py` этим файлом не изменяется и не импортируется.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from dekoder.application.conversation.dto import (
    StartNewConversationCommand,
    StartNewConversationResult,
)
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.domain.conversation.entities import Conversation


class StartNewConversation:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: StartNewConversationCommand) -> StartNewConversationResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return StartNewConversationResult(conversation_id=None)

            active_conversation = await repositories.conversations.get_active_by_user_id(user.id)
            if active_conversation is not None:
                active_conversation.close(datetime.now(UTC))
                await repositories.conversations.close(active_conversation)

            new_conversation = self._build_conversation(user_id=user.id)
            saved_conversation = await repositories.conversations.save(new_conversation)

            return StartNewConversationResult(conversation_id=saved_conversation.id)

    @staticmethod
    def _build_conversation(user_id: UUID) -> Conversation:
        """UUID и UTC created_at/updated_at — тем же способом, что и `ProcessUserMessage._build_message`."""
        now = datetime.now(UTC)
        return Conversation(
            id=uuid4(),
            user_id=user_id,
            created_at=now,
            updated_at=now,
            closed_at=None,
        )
