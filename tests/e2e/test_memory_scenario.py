"""
Сквозные сценарии Sprint 5 (задача S5-07, ADR-5.9/5.10) — тот же харнесс,
что и `tests/e2e/test_profile_scenario.py`: реальный `telegram.ext.
Application`, реальные обработчики `presentation/telegram/handlers/
memory.py`, реальные SQLAlchemy-репозитории (`bootstrap/repositories.py`)
поверх временной SQLite (`tmp_path`, схема — `Base.metadata.create_all()`).
Никакого LLM в этих сценариях — `/remember`/`/memory`/callback-удаление
не вызывают `ProcessUserMessage`/`LLMProvider`.

Сценарии:

    1. TestRememberAndList        — /remember сохраняет факт, /memory его показывает с кнопкой 🗑;
    2. TestEmptyRememberText      — /remember без текста просит написать факт следующим
       сообщением и выставляет PENDING_REMEMBER_KEY (Sprint 12), не падает;
    3. TestEmptyMemoryList        — /memory без сохранённых фактов — дружелюбное сообщение;
    4. TestDeleteViaCallback      — нажатие 🗑 удаляет запись, список обновляется;
    5. TestCrossUserDeleteIsRejected — пользователь A не может удалить запись пользователя B
       даже подделав callback_data с чужим id (ADR-5.10);
    6. TestNoForgetCommand        — `/forget` не зарегистрирован (ADR-5.10);
    7. TestRememberAndDeleteAuditLog — Sprint 9, задача S9-05/S9-07 (ADR-9.4):
       /remember -> callback-удаление, тем же сквозным харнессом (реальный
       `telegram.ext.Application`, реальные SQLAlchemy-репозитории поверх
       временной SQLite), подтверждает появление `memory_record_created`/
       `memory_record_deleted` с `audit=True` — формализует живую проверку,
       выполненную вручную в работающем Docker-контейнере при S9-07.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.memory.dto import ListMemoryRecordsCommand
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.presentation.telegram.bot import build_telegram_application, register_memory_handlers
from dekoder.presentation.telegram.handlers.memory import (
    MEMORY_EMPTY_MESSAGE,
    PENDING_REMEMBER_KEY,
    REMEMBER_PROMPT_MESSAGE,
    REMEMBER_SAVED_MESSAGE,
)
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.logging import configure_logging

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


def _make_text_update(text: str, user_id: int) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_context() -> MagicMock:
    """`user_data` — настоящий `dict` (не `MagicMock`), чтобы можно было проверить выставленный флаг."""
    return MagicMock(user_data={})


def _make_callback_update(record_id: UUID, user_id: int) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_message = None
    update.effective_user = MagicMock(id=user_id)
    query = MagicMock()
    query.data = f"memory_delete:{record_id}"
    query.from_user = MagicMock(id=user_id)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


def _build_application(
    create_memory_record: CreateMemoryRecordUseCase,
    list_memory_records: ListMemoryRecordsUseCase,
    delete_memory_record: DeleteMemoryRecordUseCase,
) -> Application:
    """Собирает реальный `telegram.ext.Application`, тот же принцип, что и `telegram_main.py::_startup`."""
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_memory_handlers(application, create_memory_record, list_memory_records, delete_memory_record)
    return application


def _handler_callbacks(application: Application) -> dict[str, object]:
    registered = application.handlers[0]
    callbacks: dict[str, object] = {}
    for handler in registered:
        if isinstance(handler, CommandHandler):
            callbacks[next(iter(handler.commands))] = handler.callback
        elif isinstance(handler, CallbackQueryHandler):
            callbacks["memory_delete_callback"] = handler.callback
    return callbacks


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-memory.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def repositories_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> ConversationRepositoriesFactory:
    return build_conversation_repositories_factory(session_factory)


@pytest.fixture
def use_cases(
    repositories_factory: ConversationRepositoriesFactory,
) -> tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase]:
    return (
        CreateMemoryRecordUseCase(repositories=repositories_factory),
        ListMemoryRecordsUseCase(repositories=repositories_factory),
        DeleteMemoryRecordUseCase(repositories=repositories_factory),
    )


class TestRememberAndList:
    """Сценарий 1 (AC-1): /remember сохраняет факт, /memory показывает его с кнопкой удаления."""

    async def test_remember_then_memory_shows_the_fact_with_delete_button(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        remember_update = _make_text_update("/remember Люблю кофе", user_id=6001)
        await callbacks["remember"](remember_update, MagicMock())  # type: ignore[operator]
        remember_update.effective_message.reply_text.assert_awaited_once_with(REMEMBER_SAVED_MESSAGE)

        memory_update = _make_text_update("/memory", user_id=6001)
        await callbacks["memory"](memory_update, MagicMock())  # type: ignore[operator]

        memory_update.effective_message.reply_text.assert_awaited_once()
        call = memory_update.effective_message.reply_text.call_args
        assert "Люблю кофе" in call.args[0]
        keyboard = call.kwargs["reply_markup"]
        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].callback_data.startswith("memory_delete:")


class TestEmptyRememberText:
    """
    Сценарий 2 (Sprint 12): /remember без текста просит написать факт
    следующим сообщением и выставляет `PENDING_REMEMBER_KEY` — не падает
    и не сохраняет пустую запись. Завершение этого сценария (следующее
    сообщение сохраняется как факт) — `TestPendingRememberCompletion`
    в `tests/unit/presentation/telegram/test_messages_handler.py`
    (`TextMessageHandler` в этом файле не зарегистрирован, только
    `register_memory_handlers`).
    """

    async def test_remember_without_text_prompts_and_sets_pending_flag(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        update = _make_text_update("/remember", user_id=6002)
        context = _make_context()
        await callbacks["remember"](update, context)  # type: ignore[operator]

        update.effective_message.reply_text.assert_awaited_once_with(REMEMBER_PROMPT_MESSAGE)
        assert context.user_data[PENDING_REMEMBER_KEY] is True

        _, list_memory_records, _ = use_cases

        result = await list_memory_records.execute(
            ListMemoryRecordsCommand(telegram_user_id=6002, correlation_id=CorrelationId("corr-1"))
        )
        assert result.records == ()

    async def test_remember_with_only_whitespace_also_prompts(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        update = _make_text_update("/remember    ", user_id=6003)
        context = _make_context()
        await callbacks["remember"](update, context)  # type: ignore[operator]

        update.effective_message.reply_text.assert_awaited_once_with(REMEMBER_PROMPT_MESSAGE)
        assert context.user_data[PENDING_REMEMBER_KEY] is True


class TestEmptyMemoryList:
    """Сценарий 3: /memory без сохранённых фактов — дружелюбное сообщение, не пустая клавиатура."""

    async def test_memory_with_no_saved_facts_shows_friendly_message(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        update = _make_text_update("/memory", user_id=6004)
        await callbacks["memory"](update, MagicMock())  # type: ignore[operator]

        update.effective_message.reply_text.assert_awaited_once_with(MEMORY_EMPTY_MESSAGE)


class TestDeleteViaCallback:
    """Сценарий 4: нажатие 🗑 удаляет запись памяти, обновлённый список её больше не содержит."""

    async def test_deleting_via_callback_removes_the_fact_from_the_list(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        await callbacks["remember"](_make_text_update("/remember Живу в Берлине", user_id=6005), MagicMock())  # type: ignore[operator]
        memory_update = _make_text_update("/memory", user_id=6005)
        await callbacks["memory"](memory_update, MagicMock())  # type: ignore[operator]
        keyboard = memory_update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        record_id = UUID(keyboard.inline_keyboard[0][0].callback_data.removeprefix("memory_delete:"))

        callback_update = _make_callback_update(record_id, user_id=6005)
        await callbacks["memory_delete_callback"](callback_update, MagicMock())  # type: ignore[operator]

        callback_update.callback_query.answer.assert_awaited_once()
        callback_update.callback_query.edit_message_text.assert_awaited_once_with(MEMORY_EMPTY_MESSAGE)

        _, list_memory_records, _ = use_cases

        result = await list_memory_records.execute(
            ListMemoryRecordsCommand(telegram_user_id=6005, correlation_id=CorrelationId("corr-1"))
        )
        assert result.records == ()


class TestCrossUserDeleteIsRejected:
    """
    Сценарий 5 (ADR-5.10, AC-2 backlog_5_tasks.md S5-07): пользователь A
    не может удалить запись пользователя B, даже подделав `callback_data`
    с id чужой записи.
    """

    async def test_user_b_cannot_delete_user_as_record_via_crafted_callback(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        create_memory_record, list_memory_records, _ = use_cases
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        await callbacks["remember"](_make_text_update("/remember Секрет пользователя A", user_id=7001), MagicMock())  # type: ignore[operator]

        listing_a = await list_memory_records.execute(
            ListMemoryRecordsCommand(telegram_user_id=7001, correlation_id=CorrelationId("corr-1"))
        )
        assert len(listing_a.records) == 1
        record_a_id = listing_a.records[0].id

        # Пользователь B (никогда не видевший запись A) шлёт callback с чужим record_id.
        crafted_callback = _make_callback_update(record_a_id, user_id=7002)
        await callbacks["memory_delete_callback"](crafted_callback, MagicMock())  # type: ignore[operator]

        crafted_callback.callback_query.answer.assert_awaited_once()
        # Отказ, не тихая отписка: B получает свой (пустой) список, не подтверждение чужого удаления.
        crafted_callback.callback_query.edit_message_text.assert_awaited_once_with(MEMORY_EMPTY_MESSAGE)

        listing_a_after = await list_memory_records.execute(
            ListMemoryRecordsCommand(telegram_user_id=7001, correlation_id=CorrelationId("corr-1"))
        )
        assert len(listing_a_after.records) == 1
        assert listing_a_after.records[0].id == record_a_id


class TestNoForgetCommand:
    """Сценарий 6 (ADR-5.10): `/forget` не зарегистрирован — удаление только через inline-кнопку."""

    def test_forget_command_is_not_registered(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
    ) -> None:
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        assert "forget" not in callbacks
        # "start" — регистрируется build_telegram_application() безусловно (не входит в объём этой задачи).
        assert set(callbacks) == {"start", "remember", "memory", "memory_delete_callback"}


class TestRememberAndDeleteAuditLog:
    """
    Сценарий 7, Sprint 9 (задача S9-05/S9-07, ADR-9.4): тем же сквозным
    харнессом (реальный `Application`, реальные SQLAlchemy-репозитории
    поверх временной SQLite), что и сценарии 1/4 выше, подтверждает, что
    `/remember` и callback-удаление порождают `memory_record_created`/
    `memory_record_deleted` с маркером `audit=True`
    (`shared/logging.py::log_audit_event`) — формализует живую проверку,
    выполненную вручную в работающем Docker-контейнере при S9-07
    (`docker compose exec` + реальный DI-контейнер против реальной БД).
    """

    async def test_remember_then_delete_emit_audit_marked_events(
        self,
        use_cases: tuple[CreateMemoryRecordUseCase, ListMemoryRecordsUseCase, DeleteMemoryRecordUseCase],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        configure_logging(environment="test")
        application = _build_application(*use_cases)
        callbacks = _handler_callbacks(application)

        remember_update = _make_text_update("/remember S9-07 сквозная проверка аудита", user_id=6006)
        await callbacks["remember"](remember_update, MagicMock())  # type: ignore[operator]
        remember_update.effective_message.reply_text.assert_awaited_once_with(REMEMBER_SAVED_MESSAGE)

        memory_update = _make_text_update("/memory", user_id=6006)
        await callbacks["memory"](memory_update, MagicMock())  # type: ignore[operator]
        keyboard = memory_update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        record_id = UUID(keyboard.inline_keyboard[0][0].callback_data.removeprefix("memory_delete:"))

        callback_update = _make_callback_update(record_id, user_id=6006)
        await callbacks["memory_delete_callback"](callback_update, MagicMock())  # type: ignore[operator]

        # Sprint 5 use case'ы (`create_memory_record.py`/`delete_memory_record.py`)
        # логируют те же имена событий без `audit=True` — фильтруем именно по
        # маркеру аудита (`log_audit_event`), не только по имени события.
        entries = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        audit_created = [
            entry for entry in entries if entry["event"] == "memory_record_created" and entry.get("audit") is True
        ]
        audit_deleted = [
            entry for entry in entries if entry["event"] == "memory_record_deleted" and entry.get("audit") is True
        ]

        assert len(audit_created) == 1
        assert audit_created[0]["record_id"] == str(record_id)
        assert audit_created[0]["correlation_id"]

        assert len(audit_deleted) == 1
        assert audit_deleted[0]["record_id"] == str(record_id)
        assert audit_deleted[0]["correlation_id"]
