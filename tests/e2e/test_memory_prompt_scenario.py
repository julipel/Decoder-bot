"""
Сквозной сценарий 4 «Долговременная память» (`План реализации.md` §18.4,
Sprint 5, задача S5-08): пользователь сохраняет факт (`/remember`),
начинает новый диалог (`/new`), отправляет обычное сообщение — собранный
`system_prompt` содержит сохранённый факт.

Тот же харнесс, что и `tests/e2e/test_profile_scenario.py`/
`tests/e2e/test_memory_scenario.py`: реальный `telegram.ext.Application`,
реальные обработчики `presentation/telegram/`, реальные SQLAlchemy-
репозитории (`bootstrap/repositories.py`) поверх временной SQLite
(`tmp_path`, схема — `Base.metadata.create_all()`), единственная
подмена — `FakeLLMProvider`.

`request.system_prompt` (то, что реально получает `FakeLLMProvider.
generate()`) — не приближение к `PromptBuildResult.system_prompt`, а то
же самое значение: `ProcessUserMessage.execute()` строит `LLMRequest.
system_prompt=build_result.system_prompt` без единого преобразования
(ADR-4.1, «тривиальный транслятор») — проверка `request.system_prompt`
эквивалентна прямой проверке `PromptBuildResult.system_prompt`.

Сценарии:

    1. TestRememberNewMessageUsesTheFact — /remember -> /new -> сообщение
       -> system_prompt содержит факт (буквально «Сценарий 4» §18.4);
    2. TestMemoryIsolatedBetweenUsers    — факт пользователя A никогда не
       появляется в промпте пользователя B;
    3. TestClearAndNewPreserveMemory     — /clear и /new не удаляют
       memory_records (факт виден в /memory после очистки истории);
    4. TestSensitiveDataRedactionOverRealDatabase — ADR-5.8/5.12 поверх
       РЕАЛЬНОГО `SQLAlchemyMemoryRepository` (не fake-репозитория, как
       в `tests/unit/application/test_memory_use_cases.py`, S5-05) —
       создание/удаление чувствительной записи не публикует её текст в
       JSON-вывод `shared/logging.py`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.application.memory.dto import (
    CreateMemoryRecordCommand,
    DeleteMemoryRecordCommand,
    ListMemoryRecordsCommand,
)
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.domain.memory.value_objects import MemorySource, MemoryStatus
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_clear_conversation_handler,
    register_memory_handlers,
    register_message_handler,
    register_new_conversation_handler,
)
from dekoder.shared.logging import clear_request_context, configure_logging

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class FakeLLMProvider:
    """Единственная подмена во всей цепочке — без сети, без OpenRouterLLMAdapter."""

    def __init__(self, response: LLMResponse | None = None) -> None:
        self._response = response
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        assert self._response is not None
        return self._response


def _response(text: str = "Здравствуйте!") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("openrouter"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_text_update(text: str, user_id: int) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory, provider: FakeLLMProvider
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=repositories_factory,
        prompt_builder=make_test_prompt_builder(),
        knowledge_search=FakeKnowledgeSearchService(),
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
        max_relevant_memory=5,
    )


def _build_application(repositories_factory: ConversationRepositoriesFactory, provider: FakeLLMProvider) -> Application:
    """Собирает реальный `telegram.ext.Application` с текстом/`/new`/`/clear`/`/remember`/`/memory`."""
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(application, _make_process_user_message(repositories_factory, provider))
    register_new_conversation_handler(application, StartNewConversation(repositories=repositories_factory))
    register_clear_conversation_handler(application, ClearConversation(repositories=repositories_factory))
    register_memory_handlers(
        application,
        CreateMemoryRecordUseCase(repositories=repositories_factory),
        ListMemoryRecordsUseCase(repositories=repositories_factory),
        DeleteMemoryRecordUseCase(repositories=repositories_factory),
    )
    return application


def _handler_callbacks(application: Application) -> dict[str, object]:
    registered = application.handlers[0]
    callbacks: dict[str, object] = {}
    for handler in registered:
        if isinstance(handler, CommandHandler):
            callbacks[next(iter(handler.commands))] = handler.callback
        elif isinstance(handler, MessageHandler):
            callbacks["text"] = handler.callback
        elif isinstance(handler, CallbackQueryHandler):
            callbacks["memory_delete_callback"] = handler.callback
    return callbacks


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-memory-prompt.db'}"
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


@pytest.fixture(autouse=True)
async def _seed_default_profile(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """
    `Base.metadata.create_all()` создаёт только схему, без сид-данных
    (сид-профили вносятся исключительно Alembic-миграцией S3-04) —
    `ProcessUserMessage`/`get_active_profile` требуют хотя бы один
    `is_default=True` профиль, иначе падает `InfrastructureError`
    (`profile_active_not_found`), не связанная с предметом этого файла.
    """
    now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    async with session_factory() as session:
        session.add(
            ProfileORM(
                id=uuid4(),
                name="Деловой",
                description="Кратко и по делу.",
                system_instruction="Отвечай кратко и по делу.",
                response_style="деловой",
                target_audience="широкая аудитория",
                formality_level="формальный",
                preferred_structure="вывод в начале",
                forbidden_phrasing=[],
                preferred_model=None,
                response_length_hint=None,
                additional_constraints="",
                status="active",
                is_system=True,
                is_default=True,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


class TestRememberNewMessageUsesTheFact:
    """Сценарий 4 §18.4 «Плана реализации.md», буквально: /remember -> /new -> сообщение -> факт в system_prompt."""

    async def test_saved_fact_appears_in_system_prompt_after_new_conversation(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(repositories_factory, provider)
        callbacks = _handler_callbacks(application)

        await callbacks["remember"](  # type: ignore[operator]
            _make_text_update("/remember Я работаю Python-разработчиком", user_id=8001), MagicMock()
        )
        await callbacks["new"](_make_text_update("/new", user_id=8001), MagicMock())  # type: ignore[operator]
        await callbacks["text"](_make_text_update("Привет!", user_id=8001), MagicMock())  # type: ignore[operator]

        assert len(provider.received_requests) == 1
        # request.system_prompt == PromptBuildResult.system_prompt без
        # изменений (ADR-4.1, «тривиальный транслятор») — эквивалентная
        # проверка собранного PromptBuildResult.
        assert "Я работаю Python-разработчиком" in provider.received_requests[0].system_prompt


class TestMemoryIsolatedBetweenUsers:
    """Изоляция памяти: факт пользователя A никогда не появляется в промпте пользователя B."""

    async def test_user_bs_prompt_never_contains_user_as_fact(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider_a = FakeLLMProvider(response=_response())
        application_a = _build_application(repositories_factory, provider_a)
        callbacks_a = _handler_callbacks(application_a)
        await callbacks_a["remember"](  # type: ignore[operator]
            _make_text_update("/remember Секретный факт пользователя A", user_id=8101), MagicMock()
        )

        provider_b = FakeLLMProvider(response=_response())
        application_b = _build_application(repositories_factory, provider_b)
        callbacks_b = _handler_callbacks(application_b)
        await callbacks_b["remember"](  # type: ignore[operator]
            _make_text_update("/remember Факт пользователя B", user_id=8102), MagicMock()
        )

        await callbacks_a["text"](_make_text_update("Сообщение от A", user_id=8101), MagicMock())  # type: ignore[operator]
        await callbacks_b["text"](_make_text_update("Сообщение от B", user_id=8102), MagicMock())  # type: ignore[operator]

        prompt_a = provider_a.received_requests[0].system_prompt
        prompt_b = provider_b.received_requests[0].system_prompt

        assert "Секретный факт пользователя A" in prompt_a
        assert "Секретный факт пользователя A" not in prompt_b
        assert "Факт пользователя B" in prompt_b
        assert "Факт пользователя B" not in prompt_a


class TestClearAndNewPreserveMemory:
    """§13.5 «Плана реализации.md»: удаление диалога не удаляет подтверждённую память автоматически."""

    async def test_clear_does_not_delete_memory_records(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(repositories_factory, provider)
        callbacks = _handler_callbacks(application)

        await callbacks["remember"](  # type: ignore[operator]
            _make_text_update("/remember Люблю горные походы", user_id=8201), MagicMock()
        )
        await callbacks["text"](_make_text_update("Привет!", user_id=8201), MagicMock())  # type: ignore[operator]
        await callbacks["clear"](_make_text_update("/clear", user_id=8201), MagicMock())  # type: ignore[operator]

        list_memory_records = ListMemoryRecordsUseCase(repositories=repositories_factory)
        result = await list_memory_records.execute(ListMemoryRecordsCommand(telegram_user_id=8201))
        assert any(record.text == "Люблю горные походы" for record in result.records)

    async def test_new_does_not_delete_memory_records(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(repositories_factory, provider)
        callbacks = _handler_callbacks(application)

        await callbacks["remember"](  # type: ignore[operator]
            _make_text_update("/remember Люблю классическую музыку", user_id=8202), MagicMock()
        )
        await callbacks["text"](_make_text_update("Привет!", user_id=8202), MagicMock())  # type: ignore[operator]
        await callbacks["new"](_make_text_update("/new", user_id=8202), MagicMock())  # type: ignore[operator]

        list_memory_records = ListMemoryRecordsUseCase(repositories=repositories_factory)
        result = await list_memory_records.execute(ListMemoryRecordsCommand(telegram_user_id=8202))
        assert any(record.text == "Люблю классическую музыку" for record in result.records)


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


class TestSensitiveDataRedactionOverRealDatabase:
    """
    ADR-5.8/5.12, поверх РЕАЛЬНОГО `SQLAlchemyMemoryRepository` (не
    fake-репозитория) — доказывает, что редакция не зависит от
    конкретной реализации порта: создание/удаление записи с
    `is_sensitive=True` никогда не публикует `record.text` в JSON-вывод
    `shared/logging.py`.
    """

    async def test_create_does_not_log_text_for_sensitive_record(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        clear_request_context()
        configure_logging(environment="test")
        create_memory_record = CreateMemoryRecordUseCase(repositories=repositories_factory)
        secret_text = "Диагноз: очень личная медицинская информация о пользователе."

        await create_memory_record.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=8301,
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
        clear_request_context()

    async def test_delete_does_not_log_text_for_sensitive_record(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        clear_request_context()
        configure_logging(environment="test")
        create_memory_record = CreateMemoryRecordUseCase(repositories=repositories_factory)
        delete_memory_record = DeleteMemoryRecordUseCase(repositories=repositories_factory)
        secret_text = "Очень личный факт, который пользователь решил удалить."

        create_result = await create_memory_record.execute(
            CreateMemoryRecordCommand(
                telegram_user_id=8302,
                text=secret_text,
                status=MemoryStatus.CONFIRMED,
                source=MemorySource.USER_EXPLICIT,
                is_sensitive=True,
            )
        )
        capsys.readouterr()  # сбрасываем лог создания — под проверкой только лог удаления

        await delete_memory_record.execute(
            DeleteMemoryRecordCommand(telegram_user_id=8302, record_id=create_result.record.id)
        )

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "memory_record_deleted"
        assert "text" not in entry
        assert secret_text not in json.dumps(entry)
        clear_request_context()
