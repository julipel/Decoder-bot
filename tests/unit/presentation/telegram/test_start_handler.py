"""
Тесты presentation/telegram/handlers/start.py — без обращения к реальному
Telegram API. `ListMemoryRecordsUseCase`/`CreateMemoryRecordUseCase`
собираются по-настоящему поверх in-memory fake-репозиториев (тот же
стиль, что и `test_memory_handler.py`) — так тесты проверяют реальную
цепочку `Update -> use case -> ответ`, не подменяя use case целиком.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeMemoryRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.memory.dto import ListMemoryRecordsCommand
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryCategory, MemoryConfidence, MemorySource, MemoryStatus
from dekoder.presentation.telegram.handlers.start import (
    ASK_NAME_MESSAGE,
    CAPABILITIES_MESSAGE,
    FIRST_TIME_GREETING,
    NAME_FACT_PREFIX,
    NAME_SAVED_TEMPLATE,
    PENDING_NAME_KEY,
    RETURNING_GREETING_TEMPLATE,
    StartCommandHandler,
    save_display_name_from_text,
)
from dekoder.shared.domain.identifiers import CorrelationId

_TELEGRAM_USER_ID = 555


def _make_update(user_id: int = _TELEGRAM_USER_ID, text: str | None = "/start") -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _make_context(user_data: dict[str, object] | None = None) -> MagicMock:
    return MagicMock(user_data=user_data if user_data is not None else {})


def _make_name_record(user_id: object, name: str) -> MemoryRecord:
    now = datetime.now(UTC)
    return MemoryRecord(
        id=uuid4(),
        user_id=user_id,
        text=f"{NAME_FACT_PREFIX}{name}",
        category=MemoryCategory.PERSONAL,
        source=MemorySource.USER_EXPLICIT,
        status=MemoryStatus.CONFIRMED,
        confidence=MemoryConfidence.MEDIUM,
        is_sensitive=False,
        expires_at=None,
        updated_by="user",
        created_at=now,
        updated_at=now,
    )


class TestStartCommandHandlerFirstTime:
    async def test_asks_for_name_and_shows_capabilities(self) -> None:
        handler = StartCommandHandler(ListMemoryRecordsUseCase(repositories=make_in_memory_repositories_factory()))
        update = _make_update()

        await handler(update, _make_context())

        update.effective_message.reply_text.assert_awaited_once_with(FIRST_TIME_GREETING)

    async def test_sets_pending_name_flag(self) -> None:
        handler = StartCommandHandler(ListMemoryRecordsUseCase(repositories=make_in_memory_repositories_factory()))
        update = _make_update()
        context = _make_context()

        await handler(update, context)

        assert context.user_data[PENDING_NAME_KEY] is True

    async def test_ignores_update_without_message(self) -> None:
        handler = StartCommandHandler(ListMemoryRecordsUseCase(repositories=make_in_memory_repositories_factory()))
        update = MagicMock(spec=Update)
        update.effective_message = None

        result = await handler(update, _make_context())

        assert result is None


class TestStartCommandHandlerKnownUser:
    async def test_greets_by_stored_name_without_asking_again(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(_TELEGRAM_USER_ID)
        memory = FakeMemoryRepository([_make_name_record(user.id, "Алекс")])
        handler = StartCommandHandler(
            ListMemoryRecordsUseCase(repositories=make_in_memory_repositories_factory(users=users, memory=memory))
        )
        update = _make_update()
        context = _make_context()

        await handler(update, context)

        update.effective_message.reply_text.assert_awaited_once_with(RETURNING_GREETING_TEMPLATE.format(name="Алекс"))
        assert PENDING_NAME_KEY not in context.user_data

    async def test_other_personal_facts_without_the_name_prefix_do_not_count_as_known(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(_TELEGRAM_USER_ID)
        now = datetime.now(UTC)
        unrelated_fact = MemoryRecord(
            id=uuid4(),
            user_id=user.id,
            text="Живёт в Москве",
            category=MemoryCategory.PERSONAL,
            source=MemorySource.USER_EXPLICIT,
            status=MemoryStatus.CONFIRMED,
            confidence=MemoryConfidence.MEDIUM,
            is_sensitive=False,
            expires_at=None,
            updated_by="user",
            created_at=now,
            updated_at=now,
        )
        memory = FakeMemoryRepository([unrelated_fact])
        handler = StartCommandHandler(
            ListMemoryRecordsUseCase(repositories=make_in_memory_repositories_factory(users=users, memory=memory))
        )
        update = _make_update()

        await handler(update, _make_context())

        update.effective_message.reply_text.assert_awaited_once_with(FIRST_TIME_GREETING)


class TestMessageConstants:
    def test_first_time_greeting_combines_capabilities_and_question(self) -> None:
        assert CAPABILITIES_MESSAGE in FIRST_TIME_GREETING
        assert ASK_NAME_MESSAGE in FIRST_TIME_GREETING

    def test_returning_greeting_still_mentions_capabilities(self) -> None:
        assert CAPABILITIES_MESSAGE in RETURNING_GREETING_TEMPLATE


class TestSaveDisplayNameFromText:
    async def test_saves_a_personal_memory_record_and_confirms_by_name(self) -> None:
        create_memory_record = CreateMemoryRecordUseCase(repositories=make_in_memory_repositories_factory())
        update = _make_update(text="Алекс")
        message = update.effective_message

        await save_display_name_from_text(create_memory_record, update, message, "Алекс")

        message.reply_text.assert_awaited_once_with(NAME_SAVED_TEMPLATE.format(name="Алекс"))

    async def test_strips_surrounding_whitespace(self) -> None:
        factory = make_in_memory_repositories_factory()
        create_memory_record = CreateMemoryRecordUseCase(repositories=factory)
        list_memory_records = ListMemoryRecordsUseCase(repositories=factory)
        update = _make_update(text="  Алекс  ")
        message = update.effective_message

        await save_display_name_from_text(create_memory_record, update, message, "  Алекс  ")

        result = await list_memory_records.execute(
            ListMemoryRecordsCommand(telegram_user_id=_TELEGRAM_USER_ID, correlation_id=CorrelationId(str(uuid4())))
        )
        assert result.records[0].text == f"{NAME_FACT_PREFIX}Алекс"
