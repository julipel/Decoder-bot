"""
Тесты use case'ов памяти (application/memory/use_cases/*, Sprint 5,
задача S5-05).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` — без SQLAlchemy. Тесты редакции
логов (`TestSensitiveDataRedaction`) перехватывают реальный JSON-вывод
`shared/logging.py` через `capsys`, по образцу
`tests/unit/shared/test_logging.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.support.fake_conversation_repositories import (
    FakeMemoryRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.memory.dto import (
    ConfirmMemoryRecordCommand,
    CreateMemoryRecordCommand,
    DeleteMemoryRecordCommand,
    ListMemoryRecordsCommand,
    RejectMemoryRecordCommand,
)
from dekoder.application.memory.use_cases.confirm_memory_record import ConfirmMemoryRecordUseCase
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.application.memory.use_cases.reject_memory_record import RejectMemoryRecordUseCase
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)
from dekoder.shared.logging import clear_request_context, configure_logging


@pytest.fixture(autouse=True)
def _reset_logging_context() -> None:
    clear_request_context()
    yield
    clear_request_context()


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


def _make_record(user_id: object, **overrides: object) -> MemoryRecord:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": user_id,
        "text": "Работает Python-разработчиком.",
        "category": MemoryCategory.FACT,
        "source": MemorySource.USER_EXPLICIT,
        "status": MemoryStatus.CONFIRMED,
        "confidence": MemoryConfidence.MEDIUM,
        "is_sensitive": False,
        "expires_at": None,
        "updated_by": "user",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryRecord(**defaults)  # type: ignore[arg-type]


class TestCreateMemoryRecord:
    async def test_creates_user_automatically_and_saves_confirmed_record(self) -> None:
        """Как ProcessUserMessage (не ClearConversation/StartNewConversation): пользователь создаётся автоматически."""
        factory = make_in_memory_repositories_factory()
        use_case = CreateMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=555,
                text="Люблю кофе.",
                status=MemoryStatus.CONFIRMED,
                source=MemorySource.USER_EXPLICIT,
            )
        )

        assert result.record.text == "Люблю кофе."
        assert result.record.status is MemoryStatus.CONFIRMED
        assert result.record.source is MemorySource.USER_EXPLICIT
        assert result.record.category is MemoryCategory.OTHER
        assert result.record.confidence is MemoryConfidence.MEDIUM
        assert result.record.is_sensitive is False

    async def test_does_not_hardcode_status_inside_use_case(self) -> None:
        """ADR-5.9: status — параметр вызывающего кода, не хардкод внутри use case'а."""
        factory = make_in_memory_repositories_factory()
        use_case = CreateMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=556,
                text="Черновой факт.",
                status=MemoryStatus.PENDING,
                source=MemorySource.USER_EXPLICIT,
            )
        )

        assert result.record.status is MemoryStatus.PENDING

    async def test_respects_explicit_category_and_confidence(self) -> None:
        factory = make_in_memory_repositories_factory()
        use_case = CreateMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=557,
                text="Живёт в Берлине.",
                status=MemoryStatus.CONFIRMED,
                source=MemorySource.USER_EXPLICIT,
                category=MemoryCategory.PERSONAL,
                confidence=MemoryConfidence.HIGH,
                is_sensitive=True,
            )
        )

        assert result.record.category is MemoryCategory.PERSONAL
        assert result.record.confidence is MemoryConfidence.HIGH
        assert result.record.is_sensitive is True


class TestListMemoryRecords:
    """AC-1: список показывает только CONFIRMED."""

    async def test_returns_only_confirmed_records(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(600)
        confirmed = _make_record(user.id, status=MemoryStatus.CONFIRMED, text="confirmed")
        pending = _make_record(user.id, status=MemoryStatus.PENDING, text="pending")
        rejected = _make_record(user.id, status=MemoryStatus.REJECTED, text="rejected")
        memory = FakeMemoryRepository([confirmed, pending, rejected])
        factory = make_in_memory_repositories_factory(users=users, memory=memory)
        use_case = ListMemoryRecordsUseCase(repositories=factory)

        result = await use_case.execute(ListMemoryRecordsCommand(telegram_user_id=600))

        assert [record.id for record in result.records] == [confirmed.id]

    async def test_unknown_user_returns_empty_list_without_creating_user(self) -> None:
        users = FakeUserRepository()
        factory = make_in_memory_repositories_factory(users=users)
        use_case = ListMemoryRecordsUseCase(repositories=factory)

        result = await use_case.execute(ListMemoryRecordsCommand(telegram_user_id=601))

        assert result.records == ()
        assert await users.get_by_telegram_user_id(601) is None


class TestDeleteMemoryRecord:
    """AC-3: удаление несуществующей записи идемпотентно, не поднимает ошибку."""

    async def test_deletes_own_record(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(700)
        record = _make_record(user.id)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(users=users, memory=memory)
        use_case = DeleteMemoryRecordUseCase(repositories=factory)

        await use_case.execute(DeleteMemoryRecordCommand(telegram_user_id=700, record_id=record.id))

        assert await memory.get_by_id(record.id) is None

    async def test_deleting_unknown_record_id_does_not_raise(self) -> None:
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(701)
        factory = make_in_memory_repositories_factory(users=users)
        use_case = DeleteMemoryRecordUseCase(repositories=factory)

        await use_case.execute(DeleteMemoryRecordCommand(telegram_user_id=701, record_id=uuid4()))

    async def test_deleting_for_unknown_telegram_user_does_not_raise(self) -> None:
        factory = make_in_memory_repositories_factory()
        use_case = DeleteMemoryRecordUseCase(repositories=factory)

        await use_case.execute(DeleteMemoryRecordCommand(telegram_user_id=702, record_id=uuid4()))

    async def test_does_not_delete_another_users_record(self) -> None:
        """Изоляция пользователей (ADR-5.10) — на уровне use case + порта, не только Telegram-хендлера."""
        users = FakeUserRepository()
        owner = await users.get_or_create_by_telegram_user_id(703)
        other = await users.get_or_create_by_telegram_user_id(704)
        record = _make_record(owner.id)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(users=users, memory=memory)
        use_case = DeleteMemoryRecordUseCase(repositories=factory)

        await use_case.execute(DeleteMemoryRecordCommand(telegram_user_id=704, record_id=record.id))
        assert other is not None

        assert await memory.get_by_id(record.id) is not None


class TestConfirmAndRejectMemoryRecord:
    """
    ADR-5.9 DoD: юнит-тесты на синтетической PENDING-записи, даже если
    ничего в Sprint 5 не создаёт её через Telegram.
    """

    async def test_confirm_transitions_pending_to_confirmed(self) -> None:
        record = _make_record(uuid4(), status=MemoryStatus.PENDING)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(memory=memory)
        use_case = ConfirmMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(ConfirmMemoryRecordCommand(record_id=record.id, updated_by="admin"))

        assert result.record is not None
        assert result.record.status is MemoryStatus.CONFIRMED
        assert result.record.updated_by == "admin"

    async def test_confirm_unknown_record_id_returns_none(self) -> None:
        factory = make_in_memory_repositories_factory()
        use_case = ConfirmMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(ConfirmMemoryRecordCommand(record_id=uuid4(), updated_by="admin"))

        assert result.record is None

    async def test_reject_transitions_pending_to_rejected(self) -> None:
        record = _make_record(uuid4(), status=MemoryStatus.PENDING)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(memory=memory)
        use_case = RejectMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(RejectMemoryRecordCommand(record_id=record.id, updated_by="admin"))

        assert result.record is not None
        assert result.record.status is MemoryStatus.REJECTED

    async def test_reject_unknown_record_id_returns_none(self) -> None:
        factory = make_in_memory_repositories_factory()
        use_case = RejectMemoryRecordUseCase(repositories=factory)

        result = await use_case.execute(RejectMemoryRecordCommand(record_id=uuid4(), updated_by="admin"))

        assert result.record is None


class TestSensitiveDataRedaction:
    """AC-2: is_sensitive=True -> лог не содержит text факта (ADR-5.8/5.12)."""

    async def test_create_does_not_log_text_for_sensitive_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        factory = make_in_memory_repositories_factory()
        use_case = CreateMemoryRecordUseCase(repositories=factory)

        secret_text = "Диагноз: очень личная медицинская информация."
        await use_case.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=800,
                text=secret_text,
                status=MemoryStatus.CONFIRMED,
                source=MemorySource.USER_EXPLICIT,
                is_sensitive=True,
            )
        )

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "memory_record_created"
        assert "text" not in entry
        assert secret_text not in json.dumps(entry)

    async def test_create_logs_text_for_non_sensitive_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        factory = make_in_memory_repositories_factory()
        use_case = CreateMemoryRecordUseCase(repositories=factory)

        await use_case.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=801,
                text="Люблю чай.",
                status=MemoryStatus.CONFIRMED,
                source=MemorySource.USER_EXPLICIT,
                is_sensitive=False,
            )
        )

        entry = _read_last_log_line(capsys)
        assert entry["text"] == "Люблю чай."

    async def test_delete_does_not_log_text_for_sensitive_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(802)
        secret_text = "Очень личный факт для удаления."
        record = _make_record(user.id, is_sensitive=True, text=secret_text)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(users=users, memory=memory)
        use_case = DeleteMemoryRecordUseCase(repositories=factory)

        await use_case.execute(DeleteMemoryRecordCommand(telegram_user_id=802, record_id=record.id))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "memory_record_deleted"
        assert "text" not in entry
        assert secret_text not in json.dumps(entry)

    async def test_confirm_does_not_log_text_for_sensitive_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        secret_text = "Секретный черновой факт."
        record = _make_record(uuid4(), status=MemoryStatus.PENDING, is_sensitive=True, text=secret_text)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(memory=memory)
        use_case = ConfirmMemoryRecordUseCase(repositories=factory)

        await use_case.execute(ConfirmMemoryRecordCommand(record_id=record.id, updated_by="admin"))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "memory_record_confirmed"
        assert "text" not in entry
        assert secret_text not in json.dumps(entry)

    async def test_reject_does_not_log_text_for_sensitive_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        secret_text = "Другой секретный черновой факт."
        record = _make_record(uuid4(), status=MemoryStatus.PENDING, is_sensitive=True, text=secret_text)
        memory = FakeMemoryRepository([record])
        factory = make_in_memory_repositories_factory(memory=memory)
        use_case = RejectMemoryRecordUseCase(repositories=factory)

        await use_case.execute(RejectMemoryRecordCommand(record_id=record.id, updated_by="admin"))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "memory_record_rejected"
        assert "text" not in entry
        assert secret_text not in json.dumps(entry)
