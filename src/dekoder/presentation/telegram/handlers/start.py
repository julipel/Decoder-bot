"""Обработчик команды /start — статическое приветствие, ProcessUserMessage не задействован."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

START_MESSAGE = (
    "Здравствуйте! Я — персональный AI-ассистент «Декодер».\n"
    "Отправьте мне текстовый запрос, и я постараюсь помочь.\n\n"
    "Сейчас работает базовая версия ассистента. Память, база знаний и "
    "дополнительные режимы будут подключены на следующих этапах."
)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(START_MESSAGE)
