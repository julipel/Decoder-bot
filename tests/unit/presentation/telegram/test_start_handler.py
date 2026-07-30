"""Тесты presentation/telegram/handlers/start.py — без обращения к реальному Telegram API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from telegram import Update

from dekoder.presentation.telegram.handlers.start import START_MESSAGE, handle_start


def _make_update() -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    return update


class TestHandleStart:
    async def test_sends_the_recommended_greeting(self) -> None:
        update = _make_update()

        await handle_start(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(START_MESSAGE)

    async def test_greeting_mentions_the_assistant_name_and_current_limitations(self) -> None:
        assert "Декодер" in START_MESSAGE
        assert "Память" in START_MESSAGE

    async def test_ignores_update_without_message(self) -> None:
        update = MagicMock(spec=Update)
        update.effective_message = None

        result = await handle_start(update, MagicMock())

        assert result is None
