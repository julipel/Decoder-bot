"""Тесты presentation/telegram/bot.py::build_telegram_application — без обращения к реальному Telegram API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from telegram import Update

from dekoder.presentation.telegram.bot import (
    UNHANDLED_ERROR_MESSAGE,
    _handle_unhandled_error,
    build_telegram_application,
)

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class TestBuildTelegramApplication:
    def test_no_proxy_by_default(self) -> None:
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)

        request = application.bot.request
        assert request._client_kwargs["proxy"] is None

    def test_proxy_url_reaches_the_httpx_client(self) -> None:
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN, proxy_url="socks5://example.com:1080")

        request = application.bot.request
        assert request._client_kwargs["proxy"] == "socks5://example.com:1080"

    def test_proxy_url_also_reaches_the_dedicated_get_updates_client(self) -> None:
        """
        `telegram.Bot` держит отдельный HTTP-клиент специально для
        long-polling `getUpdates` (`Bot._request[0]`, не то же самое, что
        публичный `.request`/`Bot._request[1]`) — без этого теста прокси
        мог бы снова остаться настроенным только для обычных вызовов
        (sendMessage/getMe), а сам приём сообщений тихо шёл бы напрямую,
        в обход прокси (найдено и исправлено 2026-09-04 — см. докстринг
        `build_telegram_application`).
        """
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN, proxy_url="socks5://example.com:1080")

        get_updates_request = application.bot._request[0]
        assert get_updates_request._client_kwargs["proxy"] == "socks5://example.com:1080"

    def test_get_updates_client_is_not_the_same_object_as_the_regular_client(self) -> None:
        """Два независимых клиента, не один и тот же объект, переданный дважды — иначе пул соединений общий."""
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)

        assert application.bot._request[0] is not application.bot._request[1]

    def test_registers_a_global_error_handler(self) -> None:
        """
        Без глобального error handler'а необработанное исключение внутри
        обработчика приводит к полной тишине для пользователя —
        python-telegram-bot по умолчанию просто логирует ошибку своим
        внутренним логгером и не отвечает в чат (найдено при
        расследовании жалобы «после приветствия — тишина», 2026-09-09).
        """
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)

        assert application.error_handlers


class TestHandleUnhandledError:
    async def test_replies_with_neutral_message_when_update_has_a_message(self) -> None:
        update = MagicMock(spec=Update)
        update.effective_message = MagicMock()
        update.effective_message.reply_text = AsyncMock()
        context = MagicMock()
        context.error = RuntimeError("boom")

        await _handle_unhandled_error(update, context)

        update.effective_message.reply_text.assert_awaited_once_with(UNHANDLED_ERROR_MESSAGE)

    async def test_does_not_raise_when_update_has_no_message(self) -> None:
        update = MagicMock(spec=Update)
        update.effective_message = None
        context = MagicMock()
        context.error = RuntimeError("boom")

        await _handle_unhandled_error(update, context)  # не должно бросить исключение

    async def test_does_not_raise_when_update_is_not_a_telegram_update(self) -> None:
        """`context.error` может быть поднято до создания `Update` (например, в самом PTB) — update тогда `None`."""
        context = MagicMock()
        context.error = RuntimeError("boom")

        await _handle_unhandled_error(None, context)  # не должно бросить исключение

    async def test_does_not_raise_when_replying_itself_fails(self) -> None:
        """Сбой самой отправки ответа (например, Telegram недоступен) не должен ронять обработку дальше."""
        update = MagicMock(spec=Update)
        update.effective_message = MagicMock()
        update.effective_message.reply_text = AsyncMock(side_effect=RuntimeError("network error"))
        context = MagicMock()
        context.error = RuntimeError("boom")

        await _handle_unhandled_error(update, context)  # не должно бросить исключение
