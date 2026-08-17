"""Обработчик команды /start — статическое приветствие, ProcessUserMessage не задействован."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

START_MESSAGE = (
    "Здравствуйте! Я — персональный AI-ассистент «Декодер».\n"
    "Отправьте мне текстовый запрос, и я постараюсь помочь.\n\n"
    "Что я умею:\n"
    "— запоминаю важные факты о вас и учитываю их в ответах (/remember, /memory);\n"
    "— ищу нужное в загруженной базе знаний и подмешиваю в ответ — без отдельной команды;\n"
    "— работаю в разных профилях-персонах (/profile) и с разными AI-моделями (/model);\n"
    "— веду историю диалога (/new — начать новый, /clear — очистить текущий)."
)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(START_MESSAGE)
