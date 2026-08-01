"""
Telegram `Update` ↔ внутренние DTO — единственное место в
`presentation/telegram/`, которое знает форму `telegram.Update` и
правило разбиения длинного ответа на части. Обработчики сами `Update`
не разбирают и лимит Telegram не знают.

`to_start_new_conversation_command()` (Sprint 2, задача S2-08) — тот же
принцип, что и `to_command()`: единственное место, извлекающее
`telegram_user_id` из `update.effective_user.id` для обработчика команды
`/new` (`presentation/telegram/handlers/new_conversation.py`).
"""

from __future__ import annotations

import uuid

from telegram import Update

from dekoder.application.conversation.dto import ProcessUserMessageCommand, StartNewConversationCommand
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
