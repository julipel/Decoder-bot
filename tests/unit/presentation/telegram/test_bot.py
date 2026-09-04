"""Тесты presentation/telegram/bot.py::build_telegram_application — без обращения к реальному Telegram API."""

from __future__ import annotations

from dekoder.presentation.telegram.bot import build_telegram_application

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
