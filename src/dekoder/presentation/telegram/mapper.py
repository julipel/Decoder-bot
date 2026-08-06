"""
Telegram `Update` ↔ внутренние DTO — единственное место в
`presentation/telegram/`, которое знает форму `telegram.Update` и
правило разбиения длинного ответа на части. Обработчики сами `Update`
не разбирают и лимит Telegram не знают.

`to_start_new_conversation_command()` (Sprint 2, задача S2-08) — тот же
принцип, что и `to_command()`: единственное место, извлекающее
`telegram_user_id` из `update.effective_user.id` для обработчика команды
`/new` (`presentation/telegram/handlers/new_conversation.py`).

`to_clear_conversation_command()` (Sprint 2, задача S2-10) — тот же
принцип, для обработчика команды `/clear`
(`presentation/telegram/handlers/clear_conversation.py`).

`to_get_active_profile_command()` (Sprint 3, задача S3-08) — тот же
принцип, для обработчика команды `/profile`
(`presentation/telegram/handlers/profile.py`).

`to_select_profile_command()` (Sprint 3, задача S3-08) — первое место в
проекте, извлекающее `telegram_user_id` не из `update.effective_user`
(обычное сообщение/команда), а из `update.callback_query.from_user` —
источник идентификатора пользователя для inline-кнопок (`CallbackQuery`),
нажавшего которую пользователь мог не совпадать с автором исходного
сообщения (групповые чаты) — используем именно того, кто нажал кнопку.

`to_create_memory_record_command()`/`to_list_memory_records_command()`
(Sprint 5, задача S5-07) — тот же принцип, для обработчиков `/remember`/
`/memory`. `to_create_memory_record_command()` — место, где ADR-5.9
буквально исполняется: `status=CONFIRMED, source=USER_EXPLICIT` заданы
здесь явно (Telegram-хендлер), не хардкодятся внутри
`CreateMemoryRecordUseCase`.

`to_delete_memory_record_command()` (Sprint 5, задача S5-07, ADR-5.10) —
тот же принцип, что и `to_select_profile_command()`: `telegram_user_id`
из `update.callback_query.from_user`, не `update.effective_user`.

`to_list_available_models_command()`/`to_get_selected_model_command()`
(Sprint 7, задача S7-07) — тот же принцип, для обработчика команды
`/model` (`presentation/telegram/handlers/model.py`), по образцу
`to_get_active_profile_command()`.

`to_select_model_command()` (Sprint 7, задача S7-07, ADR-7.9) — тот же
принцип, что и `to_select_profile_command()`: `telegram_user_id` из
`update.callback_query.from_user`, не `update.effective_user`.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from telegram import Update

from dekoder.application.conversation.dto import (
    ClearConversationCommand,
    ProcessUserMessageCommand,
    StartNewConversationCommand,
)
from dekoder.application.memory.dto import (
    CreateMemoryRecordCommand,
    DeleteMemoryRecordCommand,
    ListMemoryRecordsCommand,
)
from dekoder.application.model_catalog.dto import (
    GetSelectedModelCommand,
    ListAvailableModelsCommand,
    SelectModelCommand,
)
from dekoder.application.profile.dto import GetActiveProfileCommand, SelectProfileCommand
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.memory.value_objects import MemorySource, MemoryStatus
from dekoder.shared.domain.identifiers import CorrelationId

# Реальный лимит Telegram на одно текстовое сообщение — 4096 символов;
# берём с запасом, чтобы не зависеть от точной границы.
TELEGRAM_SAFE_MESSAGE_LIMIT = 4000


def to_command(update: Update) -> ProcessUserMessageCommand:
    """
    Строит команду из входящего текстового сообщения. Текст не
    валидируется здесь — это делает `ProcessUserMessage.execute()` через
    доменный `MessageText` (не обязанность presentation-слоя). Новый
    `correlation_id` генерируется на каждое сообщение (требование 5).
    """
    message = update.effective_message
    user = update.effective_user
    if message is None or message.text is None or user is None:
        raise ValueError("Update does not contain a text message from a known user")

    return ProcessUserMessageCommand(
        telegram_user_id=user.id,
        message_text=message.text,
        correlation_id=CorrelationId(str(uuid.uuid4())),
    )


def to_start_new_conversation_command(update: Update) -> StartNewConversationCommand:
    """
    Строит команду для обработчика `/new` из входящего `Update`.
    `telegram_user_id` извлекается тем же способом, что и в `to_command()`
    — `update.effective_user.id`. Команда не содержит текста сообщения и
    `correlation_id`, как и сам `StartNewConversationCommand`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return StartNewConversationCommand(telegram_user_id=user.id)


def to_clear_conversation_command(update: Update) -> ClearConversationCommand:
    """
    Строит команду для обработчика `/clear` из входящего `Update`.
    `telegram_user_id` извлекается тем же способом, что и в `to_command()`/
    `to_start_new_conversation_command()` — `update.effective_user.id`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return ClearConversationCommand(telegram_user_id=user.id)


def to_get_active_profile_command(update: Update) -> GetActiveProfileCommand:
    """
    Строит команду для обработчика `/profile` из входящего `Update`.
    `telegram_user_id` извлекается тем же способом, что и в `to_command()`/
    `to_start_new_conversation_command()`/`to_clear_conversation_command()`
    — `update.effective_user.id`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return GetActiveProfileCommand(telegram_user_id=user.id)


def to_select_profile_command(update: Update, profile_id: UUID) -> SelectProfileCommand:
    """
    Строит команду для callback'а выбора профиля из входящего `Update`.
    `telegram_user_id` извлекается из `update.callback_query.from_user`
    (не `update.effective_user`) — пользователь, нажавший inline-кнопку,
    а не автор исходного сообщения со списком профилей.
    """
    query = update.callback_query
    if query is None or query.from_user is None:
        raise ValueError("Update does not contain a callback query from a known user")

    return SelectProfileCommand(telegram_user_id=query.from_user.id, profile_id=profile_id)


def to_create_memory_record_command(update: Update, text: str) -> CreateMemoryRecordCommand:
    """
    Строит команду для обработчика `/remember` из входящего `Update` и
    уже извлечённого текста факта (разбор `"/remember <текст>"` —
    ответственность `presentation/telegram/handlers/memory.py`, не этого
    модуля). `status=CONFIRMED, source=USER_EXPLICIT` — явно, здесь
    (ADR-5.9): `/remember` сохраняет запись сразу подтверждённой, без
    двухшагового сценария.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return CreateMemoryRecordCommand(
        telegram_user_id=user.id,
        text=text,
        status=MemoryStatus.CONFIRMED,
        source=MemorySource.USER_EXPLICIT,
    )


def to_list_memory_records_command(update: Update) -> ListMemoryRecordsCommand:
    """
    Строит команду для обработчика `/memory` из входящего `Update`.
    `telegram_user_id` извлекается тем же способом, что и в `to_command()`/
    `to_clear_conversation_command()`/`to_get_active_profile_command()` —
    `update.effective_user.id`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return ListMemoryRecordsCommand(telegram_user_id=user.id)


def to_delete_memory_record_command(update: Update, record_id: UUID) -> DeleteMemoryRecordCommand:
    """
    Строит команду для callback'а удаления записи памяти из входящего
    `Update`. `telegram_user_id` извлекается из `update.callback_query.
    from_user` (не `update.effective_user`) — тот же принцип, что и
    `to_select_profile_command()` (ADR-5.10).
    """
    query = update.callback_query
    if query is None or query.from_user is None:
        raise ValueError("Update does not contain a callback query from a known user")

    return DeleteMemoryRecordCommand(telegram_user_id=query.from_user.id, record_id=record_id)


def to_list_available_models_command(update: Update) -> ListAvailableModelsCommand:
    """
    Строит команду для обработчика `/model` из входящего `Update`.
    `telegram_user_id` извлекается тем же способом, что и в
    `to_get_active_profile_command()` — `update.effective_user.id`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return ListAvailableModelsCommand(telegram_user_id=user.id)


def to_get_selected_model_command(update: Update) -> GetSelectedModelCommand:
    """
    Строит команду для обработчика `/model` из входящего `Update` —
    используется для отображения текущего выбора (ADR-7.7) перед
    построением клавиатуры `to_list_available_models_command()`.
    """
    user = update.effective_user
    if user is None:
        raise ValueError("Update does not contain a known user")

    return GetSelectedModelCommand(telegram_user_id=user.id)


def to_select_model_command(update: Update, model_id: ModelId) -> SelectModelCommand:
    """
    Строит команду для callback'а выбора модели из входящего `Update`.
    `telegram_user_id` извлекается из `update.callback_query.from_user`
    (не `update.effective_user`) — тот же принцип, что и
    `to_select_profile_command()`/`to_delete_memory_record_command()`
    (ADR-7.9).
    """
    query = update.callback_query
    if query is None or query.from_user is None:
        raise ValueError("Update does not contain a callback query from a known user")

    return SelectModelCommand(telegram_user_id=query.from_user.id, model_id=model_id)


def split_message(text: str, limit: int = TELEGRAM_SAFE_MESSAGE_LIMIT) -> list[str]:
    """Делит текст на части не длиннее `limit`, предпочитая границу строки/слова хардкодному разрезу."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
