"""
Тесты presentation/telegram/handlers/memory.py — фокус на аудит-логах
`memory_record_created`/`memory_record_deleted` (Sprint 9, задача S9-05,
ADR-9.4). Как и `test_clear_conversation_handler.py`, use case'ы
собираются по-настоящему поверх in-memory fake-репозиториев (`tests/
support/fake_conversation_repositories.py`), без SQLAlchemy и без
реального Telegram API (`Update`/`CallbackQuery` — `MagicMock`).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeMemoryRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryCategory, MemoryConfidence, MemorySource, MemoryStatus
from dekoder.presentation.telegram.handlers.memory import MemoryDeleteCallbackHandler, RememberCommandHandler
from dekoder.shared.logging import clear_request_context, configure_logging


@pytest.fixture(autouse=True)
def _reset_logging_context() -> None:
    clear_request_context()
    yield
    clear_request_context()


def _read_log_entries(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    out = capsys.readouterr().out.strip().splitlines()
    return [json.loads(line) for line in out]


def _find_entry(entries: list[dict[str, object]], event: str) -> dict[str, object]:
    matches = [entry for entry in entries if entry.get("event") == event]
    assert matches, f"ожидалось событие {event!r}, получено: {entries!r}"
    return matches[-1]


def _make_text_update(text: str, user_id: int = 111) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _make_callback_update(record_id: object, user_id: int = 222) -> MagicMock:
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


class TestRememberCommandHandlerAuditLog:
    """AC-1 (S9-05): успешное /remember -> memory_record_created, audit=True."""

    async def test_logs_memory_record_created_with_audit_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        create_use_case = CreateMemoryRecordUseCase(repositories=make_in_memory_repositories_factory())
        handler = RememberCommandHandler(create_use_case)
        update = _make_text_update("/remember Я работаю Python-разработчиком.")

        await handler(update, MagicMock())

        entries = _read_log_entries(capsys)
        entry = _find_entry(entries, "memory_record_created")
        assert entry["audit"] is True
        assert isinstance(entry["record_id"], str) and entry["record_id"]
        # AC-3: текст факта нигде не попадает в лог.
        assert "Я работаю Python-разработчиком" not in json.dumps(entry)

    async def test_does_not_log_the_event_on_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")

        class _FailingCreateMemoryRecord:
            async def execute(self, command: object) -> None:
                raise RuntimeError("boom")

        handler = RememberCommandHandler(_FailingCreateMemoryRecord())  # type: ignore[arg-type]
        update = _make_text_update("/remember Что-то важное.")

        await handler(update, MagicMock())

        entries = _read_log_entries(capsys)
        assert not any(entry.get("event") == "memory_record_created" for entry in entries)


class TestMemoryDeleteCallbackHandlerAuditLog:
    """AC-2 (S9-05): успешное удаление -> memory_record_deleted, audit=True."""

    async def test_logs_memory_record_deleted_with_audit_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(222)
        record = MemoryRecord(
            id=uuid4(),
            user_id=user.id,
            text="Факт для удаления",
            category=MemoryCategory.OTHER,
            source=MemorySource.USER_EXPLICIT,
            status=MemoryStatus.CONFIRMED,
            confidence=MemoryConfidence.MEDIUM,
            is_sensitive=False,
            expires_at=None,
            updated_by="user",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(users=users, memory=memory)
        delete_use_case = DeleteMemoryRecordUseCase(repositories=factory)
        list_use_case = ListMemoryRecordsUseCase(repositories=factory)
        handler = MemoryDeleteCallbackHandler(delete_use_case, list_use_case)
        update = _make_callback_update(record.id, user_id=222)

        await handler(update, MagicMock())

        entries = _read_log_entries(capsys)
        entry = _find_entry(entries, "memory_record_deleted")
        assert entry["audit"] is True
        assert entry["record_id"] == str(record.id)
        # AC-3: текст факта нигде не попадает в аудит-лог хендлера.
        assert "Факт для удаления" not in json.dumps(entry)

    async def test_does_not_log_the_event_on_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")

        class _FailingDeleteMemoryRecord:
            async def execute(self, command: object) -> None:
                raise RuntimeError("boom")

        class _UnusedListMemoryRecords:
            async def execute(self, command: object) -> None:
                raise AssertionError("не должен вызываться после сбоя удаления")

        handler = MemoryDeleteCallbackHandler(
            _FailingDeleteMemoryRecord(),  # type: ignore[arg-type]
            _UnusedListMemoryRecords(),  # type: ignore[arg-type]
        )
        update = _make_callback_update(uuid4(), user_id=222)

        await handler(update, MagicMock())

        entries = _read_log_entries(capsys)
        assert not any(entry.get("event") == "memory_record_deleted" for entry in entries)
