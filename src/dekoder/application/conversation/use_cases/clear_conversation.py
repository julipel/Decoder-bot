"""
ClearConversation — use case, удаляющий все сообщения ТЕКУЩЕГО активного
диалога пользователя, не закрывая и не удаляя сам `Conversation` (Sprint 2,
задача S2-09).

Используется будущим обработчиком команды `/clear` — подключение к
Telegram Adapter является отдельной, следующей задачей Sprint 2 (S2-10);
здесь Telegram SDK не задействован вовсе.

Зависит от `ConversationRepositoriesFactory` (`application/conversation/
ports.py`) — того же порта, каким `StartNewConversation` (задача S2-07) и
`ProcessUserMessage` (задача S2-06) получают короткоживущую транзакцию с
группой репозиториев. В отличие от `StartNewConversation`, `repositories.
messages` здесь ИСПОЛЬЗУЕТСЯ — единственный вызов `.clear(conversation_id)`,
и больше ничего: ни `.save()`, ни `.history()` этот use case не вызывает.

Не зависит от SQLAlchemy, ORM-моделей, Telegram SDK и `LLMProvider` — ни
один из них не импортируется в этом файле, и конструктор не принимает
`LLMProvider` вовсе (в отличие от `ProcessUserMessage`) — LLM не участвует
в очистке истории.

Как и `StartNewConversation`, пользователь НЕ создаётся автоматически:
если `UserRepository.get_by_telegram_user_id()` возвращает `None`, use
case завершается успешно (`ClearConversationResult(status=
NO_ACTIVE_CONVERSATION, conversation_id=None, deleted_count=0)`), не
создавая ни пользователя, ни диалог. Аналогично, если у существующего
пользователя нет активного диалога — новый диалог НЕ создаётся
(`ConversationRepository.get_or_create_active` здесь намеренно не
используется — только `get_active_by_user_id`, который возвращает `None`
вместо создания диалога).

Если активный диалог найден, вызывается ровно один метод — `repositories.
messages.clear(active_conversation.id)`. `Conversation`, найденный через
`get_active_by_user_id`, дальше НИКАК не изменяется и не передаётся ни в
`repositories.conversations.save()`, ни в `repositories.conversations.
close()` — ни один из этих двух методов не вызывается ни разу в этом
файле (backlog_2_tasks.md S2-09: «не закрывать и не удалять диалог»,
«использует ТОЛЬКО существующие порты»; в контракте `ConversationRepository`
метода удаления не существует вовсе, см. `application/conversation/
ports.py`).

Вся операция — один короткий `async with self._repositories()` блок,
той же формы, что и у `StartNewConversation`: LLM не вызывается, поэтому
не нужно разделять транзакцию на части, чтобы не удерживать её во время
сетевого запроса (backlog_2.md §9).

`process_user_message.py` этим файлом не изменяется и не импортируется.
"""

from __future__ import annotations

from dekoder.application.conversation.dto import (
    ClearConversationCommand,
    ClearConversationResult,
    ClearConversationStatus,
)
from dekoder.application.conversation.ports import ConversationRepositoriesFactory


class ClearConversation:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self, command: ClearConversationCommand) -> ClearConversationResult:
        async with self._repositories() as repositories:
            user = await repositories.users.get_by_telegram_user_id(command.telegram_user_id)
            if user is None:
                return self._no_active_conversation()

            active_conversation = await repositories.conversations.get_active_by_user_id(user.id)
            if active_conversation is None:
                return self._no_active_conversation()

            deleted_count = await repositories.messages.clear(active_conversation.id)
            status = ClearConversationStatus.CLEARED if deleted_count > 0 else ClearConversationStatus.ALREADY_EMPTY
            return ClearConversationResult(
                status=status,
                conversation_id=active_conversation.id,
                deleted_count=deleted_count,
            )

    @staticmethod
    def _no_active_conversation() -> ClearConversationResult:
        return ClearConversationResult(
            status=ClearConversationStatus.NO_ACTIVE_CONVERSATION,
            conversation_id=None,
            deleted_count=0,
        )
