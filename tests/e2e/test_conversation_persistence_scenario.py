"""
Сквозные сценарии Sprint 2 поверх РЕАЛЬНОГО постоянного хранилища
(задача S2-11, «Финальная интеграция и E2E-проверка Sprint 2»).

`tests/e2e/test_conversation_scenario.py` уже проверяет цепочку
`Telegram Handler -> ProcessUserMessage -> LLMProvider -> ответ` поверх
in-memory fake-репозиториев (`tests/support/fake_conversation_repositories.py`)
— этого достаточно для маршрутизации/DI/ошибок, но недостаточно для
восьми обязательных сценариев backlog_2_tasks.md (S2-11), которые прямо
требуют проверки того, что данные «физически сохраняются в БД» и
переживают «перезапуск приложения» (т.е. новый `AsyncEngine` поверх того
же файла).

Этот файл — тот же харнесс (реальный `telegram.ext.Application`, реальные
`ProcessUserMessage`/`StartNewConversation`/`ClearConversation`, реальные
хендлеры `presentation/telegram/`), но поверх РЕАЛЬНЫХ SQLAlchemy-
репозиториев (`bootstrap/repositories.py`) и временной SQLite (`tmp_path`,
схема — `Base.metadata.create_all()`, то же допустимое исключение для
тестового окружения, что и в `tests/integration/test_*_persistence.py`,
backlog_2.md §3). Единственная подмена во всей цепочке — `FakeLLMProvider`
(без сети, без реального Telegram API и без `OpenRouterLLMAdapter`).

Восемь обязательных сценариев (backlog_2_tasks.md, S2-11):

    1. TestFirstAndSecondRequest    — первый и (2) второй запрос;
    3. TestNewCommand               — /new закрывает старый, создаёт новый;
    4. TestClearCommand             — /clear чистит историю, диалог жив;
    5. TestUserIsolation            — сообщения двух пользователей не смешиваются;
    6. TestApplicationRestart       — данные переживают новый AsyncEngine;
    7. TestLlmError                 — ошибка LLM не теряет user message;
    8. TestDatabaseError            — ошибка БД откатывается, LLM не вызывается.

Прикладной поток (`ProcessUserMessage`/`StartNewConversation`/
`ClearConversation`/репозитории/Alembic-схема) не изменялся ради этого
файла — сценарии дополняют, а не заменяют уже существующие
`tests/integration/test_process_user_message_persistence.py`,
`tests/integration/test_start_new_conversation_persistence.py`,
`tests/integration/test_clear_conversation_persistence.py`,
`tests/integration/test_repositories_bootstrap.py` (которые проверяют то
же самое на уровне use case/репозиториев напрямую, без Telegram-слоя).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import ConversationRepositories, ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.bootstrap.repositories import (
    build_conversation_repositories_factory,
    build_conversation_repository,
    build_memory_repository,
    build_message_repository,
    build_profile_repository,
    build_user_repository,
)
from dekoder.domain.conversation.entities import Message
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory, session_scope
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_clear_conversation_handler,
    register_message_handler,
    register_new_conversation_handler,
)
from dekoder.presentation.telegram.handlers.clear_conversation import CONVERSATION_CLEARED_MESSAGE
from dekoder.presentation.telegram.handlers.new_conversation import NEW_CONVERSATION_STARTED_MESSAGE
from dekoder.shared.errors import InfrastructureError, LLMProviderError

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class FakeLLMProvider:
    """Единственная подмена во всей цепочке — без сети, без OpenRouterLLMAdapter."""

    def __init__(self, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.call_count = 0
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        self.received_requests.append(request)
        if self._error is not None:
            raise self._error
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


def _make_update(text: str | None = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory,
    provider: FakeLLMProvider,
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=repositories_factory,
        prompt_builder=make_test_prompt_builder(),
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
    )


def _build_application(
    process_user_message: ProcessUserMessage,
    start_new_conversation: StartNewConversation | None = None,
    clear_conversation: ClearConversation | None = None,
) -> Application:
    """
    Собирает реальный `telegram.ext.Application` тем же способом, что и
    `telegram_main.py::_startup` — только композиция обработчиков,
    поверх уже готовых use cases (никакого DI внутри этой функции самой
    по себе, кроме передачи уже собранных зависимостей дальше).
    """
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(application, process_user_message)
    if start_new_conversation is not None:
        register_new_conversation_handler(application, start_new_conversation)
    if clear_conversation is not None:
        register_clear_conversation_handler(application, clear_conversation)
    return application


def _handler_callbacks(application: Application) -> dict[str, object]:
    """
    Достаёт callback'и уже зарегистрированных хендлеров по имени команды
    (`"new"`/`"clear"`) либо `"text"` для обычных сообщений — без
    обращения к сети (`Application.process_update()` потребовал бы
    `Application.initialize()` -> реальный Telegram `getMe`).
    """
    registered = application.handlers[0]
    callbacks: dict[str, object] = {}
    for handler in registered:
        if isinstance(handler, CommandHandler):
            callbacks[next(iter(handler.commands))] = handler.callback
        elif isinstance(handler, MessageHandler):
            callbacks["text"] = handler.callback
    return callbacks


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-persistence.db'}"
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
async def _default_profile(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """
    `Base.metadata.create_all()` (используется во всём этом файле) создаёт
    только схему, без сид-данных (сид-профили вносятся исключительно
    Alembic-миграцией S3-04, ADR-3.4). С задачи S3-07 `ProcessUserMessage`
    требует хотя бы один активный профиль с `is_default=True`, иначе
    `get_active_profile` поднимает `InfrastructureError` — тестовое
    окружение вставляет один профиль напрямую через `ProfileORM`.
    """
    await _seed_default_profile(session_factory)


async def _seed_default_profile(session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    async with session_factory() as session:
        session.add(
            ProfileORM(
                id=uuid4(),
                name="Тестовый",
                description="Тестовый профиль по умолчанию.",
                system_instruction="Ты — ассистент.",
                response_style="нейтральный",
                target_audience="тесты",
                formality_level="нейтральный",
                preferred_structure="без требований",
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


async def _all_users(session_factory: async_sessionmaker[AsyncSession]) -> list[UserORM]:
    async with session_factory() as session:
        return list((await session.execute(select(UserORM))).scalars().all())


async def _all_conversations(session_factory: async_sessionmaker[AsyncSession]) -> list[ConversationORM]:
    async with session_factory() as session:
        return list((await session.execute(select(ConversationORM))).scalars().all())


async def _messages_of(session_factory: async_sessionmaker[AsyncSession], conversation_id: UUID) -> list[MessageORM]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(MessageORM)
                .where(MessageORM.conversation_id == conversation_id)
                .order_by(MessageORM.created_at, MessageORM.id)
            )
        ).scalars()
        return list(rows)


class TestFirstAndSecondRequest:
    """Обязательные сценарии 1 и 2: первый и второй запрос одного пользователя."""

    async def test_first_message_creates_user_conversation_and_both_messages(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callbacks = _handler_callbacks(application)
        update = _make_update(text="Привет!", user_id=111)

        await callbacks["text"](update, MagicMock())  # type: ignore[operator]

        users = await _all_users(session_factory)
        assert len(users) == 1
        assert users[0].telegram_user_id == 111

        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 1
        assert conversations[0].user_id == users[0].id
        assert conversations[0].closed_at is None

        messages = await _messages_of(session_factory, conversations[0].id)
        assert [m.role for m in messages] == ["user", "assistant"]
        assert [m.content for m in messages] == ["Привет!", "Здравствуйте!"]

    async def test_second_message_reuses_user_and_conversation_and_llm_sees_full_history(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Ответ"))
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_update(text="Сообщение 1", user_id=222), MagicMock())  # type: ignore[operator]
        await callbacks["text"](_make_update(text="Сообщение 2", user_id=222), MagicMock())  # type: ignore[operator]

        users = await _all_users(session_factory)
        assert len(users) == 1  # не создан второй пользователь

        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 1  # не создан второй диалог

        messages = await _messages_of(session_factory, conversations[0].id)
        assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]

        assert provider.call_count == 2
        second_request_roles = [m.role for m in provider.received_requests[1].messages]
        second_request_contents = [m.content for m in provider.received_requests[1].messages]
        assert second_request_roles == ["user", "assistant", "user"]
        assert second_request_contents == ["Сообщение 1", "Ответ", "Сообщение 2"]


class TestNewCommand:
    """Обязательный сценарий 3: /new закрывает старый диалог и создаёт новый."""

    async def test_new_command_closes_old_conversation_starts_new_and_keeps_old_messages(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        process_user_message = _make_process_user_message(repositories_factory, provider)
        start_new_conversation = StartNewConversation(repositories=repositories_factory)
        application = _build_application(process_user_message, start_new_conversation=start_new_conversation)
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_update(text="Привет!", user_id=333), MagicMock())  # type: ignore[operator]
        conversations_before = await _all_conversations(session_factory)
        assert len(conversations_before) == 1
        old_conversation_id = conversations_before[0].id

        new_update = _make_update(text="/new", user_id=333)
        await callbacks["new"](new_update, MagicMock())  # type: ignore[operator]
        new_update.effective_message.reply_text.assert_awaited_once_with(NEW_CONVERSATION_STARTED_MESSAGE)

        conversations_after = await _all_conversations(session_factory)
        assert len(conversations_after) == 2
        old_row = next(c for c in conversations_after if c.id == old_conversation_id)
        new_row = next(c for c in conversations_after if c.id != old_conversation_id)
        assert old_row.closed_at is not None  # старый диалог закрыт
        assert new_row.closed_at is None  # новый диалог активен

        # старые сообщения физически сохранены в БД
        old_messages = await _messages_of(session_factory, old_conversation_id)
        assert [m.content for m in old_messages] == ["Привет!", "Здравствуйте!"]

        # новая история начинается с нуля
        assert await _messages_of(session_factory, new_row.id) == []

        # следующее сообщение записывается в НОВЫЙ conversation_id
        await callbacks["text"](_make_update(text="Снова привет", user_id=333), MagicMock())  # type: ignore[operator]
        new_messages = await _messages_of(session_factory, new_row.id)
        assert [m.content for m in new_messages] == ["Снова привет", "Здравствуйте!"]

        # старые сообщения не тронуты (сравнение по id/content — ORM-объекты
        # из разных запросов не равны друг другу по identity, только по данным)
        old_messages_after = await _messages_of(session_factory, old_conversation_id)
        assert [(m.id, m.content) for m in old_messages_after] == [(m.id, m.content) for m in old_messages]


class TestClearCommand:
    """Обязательный сценарий 4: /clear удаляет историю, диалог остаётся активным."""

    async def test_clear_command_deletes_history_but_keeps_same_active_conversation(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        process_user_message = _make_process_user_message(repositories_factory, provider)
        clear_conversation = ClearConversation(repositories=repositories_factory)
        application = _build_application(process_user_message, clear_conversation=clear_conversation)
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_update(text="Привет!", user_id=444), MagicMock())  # type: ignore[operator]
        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 1
        conversation_id = conversations[0].id
        assert len(await _messages_of(session_factory, conversation_id)) == 2

        clear_update = _make_update(text="/clear", user_id=444)
        await callbacks["clear"](clear_update, MagicMock())  # type: ignore[operator]
        clear_update.effective_message.reply_text.assert_awaited_once_with(CONVERSATION_CLEARED_MESSAGE)

        # текущая история физически удалена
        assert await _messages_of(session_factory, conversation_id) == []

        # Conversation остаётся тем же самым, активным диалогом
        conversations_after = await _all_conversations(session_factory)
        assert len(conversations_after) == 1
        assert conversations_after[0].id == conversation_id
        assert conversations_after[0].closed_at is None

        # следующее сообщение сохраняется в ТОМ ЖЕ Conversation
        await callbacks["text"](_make_update(text="Заново", user_id=444), MagicMock())  # type: ignore[operator]
        messages_after = await _messages_of(session_factory, conversation_id)
        assert [m.content for m in messages_after] == ["Заново", "Здравствуйте!"]
        assert len(await _all_conversations(session_factory)) == 1  # новый диалог не создан


class TestUserIsolation:
    """Обязательный сценарий 5: сообщения двух пользователей не смешиваются."""

    async def test_two_users_get_separate_conversations_and_histories(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Ответ"))
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_update(text="От первого пользователя", user_id=501), MagicMock())  # type: ignore[operator]
        await callbacks["text"](_make_update(text="От второго пользователя", user_id=502), MagicMock())  # type: ignore[operator]

        users = await _all_users(session_factory)
        assert {u.telegram_user_id for u in users} == {501, 502}

        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 2
        assert len({c.user_id for c in conversations}) == 2  # у каждого свой Conversation
        assert all(c.closed_at is None for c in conversations)  # оба активны

        user_501 = next(u for u in users if u.telegram_user_id == 501)
        user_502 = next(u for u in users if u.telegram_user_id == 502)
        conversation_501 = next(c for c in conversations if c.user_id == user_501.id)
        conversation_502 = next(c for c in conversations if c.user_id == user_502.id)

        messages_501 = await _messages_of(session_factory, conversation_501.id)
        messages_502 = await _messages_of(session_factory, conversation_502.id)
        assert [m.content for m in messages_501] == ["От первого пользователя", "Ответ"]
        assert [m.content for m in messages_502] == ["От второго пользователя", "Ответ"]


class TestApplicationRestart:
    """
    Обязательный сценарий 6: закрыть текущий `AsyncEngine`/сессии, собрать
    НОВЫЙ контейнер (новый `AsyncEngine`/`async_sessionmaker`/репозитории/
    use cases/Telegram-хендлеры) поверх ТОГО ЖЕ файла SQLite и убедиться,
    что пользователи/диалоги/сообщения доступны, а следующее сообщение
    продолжает существующий диалог.
    """

    async def test_data_survives_restart_and_conversation_continues(self, tmp_path: Path) -> None:
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'restart.db'}"

        first_engine = create_database_engine(database_url)
        async with first_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        first_session_factory = create_session_factory(first_engine)
        await _seed_default_profile(first_session_factory)
        first_repositories_factory = build_conversation_repositories_factory(first_session_factory)

        provider_before_restart = FakeLLMProvider(response=_response("Ответ до перезапуска"))
        application_before = _build_application(
            _make_process_user_message(first_repositories_factory, provider_before_restart)
        )
        callbacks_before = _handler_callbacks(application_before)
        await callbacks_before["text"](  # type: ignore[operator]
            _make_update(text="Привет!", user_id=601), MagicMock()
        )

        conversations_before = await _all_conversations(first_session_factory)
        assert len(conversations_before) == 1
        conversation_id = conversations_before[0].id

        # "Перезапуск приложения": закрываем текущий AsyncEngine — все его
        # соединения/сессии становятся непригодны, как при остановке процесса.
        await first_engine.dispose()

        # Собираем НОВЫЙ контейнер поверх ТОГО ЖЕ файла БД, как это делает
        # telegram_main.py::_startup после перезапуска процесса.
        second_engine = create_database_engine(database_url)
        try:
            second_session_factory = create_session_factory(second_engine)
            second_repositories_factory = build_conversation_repositories_factory(second_session_factory)

            # пользователи/диалоги/сообщения по-прежнему доступны
            users_after_restart = await _all_users(second_session_factory)
            assert len(users_after_restart) == 1
            assert users_after_restart[0].telegram_user_id == 601

            messages_after_restart = await _messages_of(second_session_factory, conversation_id)
            assert [m.content for m in messages_after_restart] == ["Привет!", "Ответ до перезапуска"]

            # следующее сообщение продолжает СУЩЕСТВУЮЩИЙ диалог
            provider_after_restart = FakeLLMProvider(response=_response("Ответ после перезапуска"))
            application_after = _build_application(
                _make_process_user_message(second_repositories_factory, provider_after_restart)
            )
            callbacks_after = _handler_callbacks(application_after)
            await callbacks_after["text"](  # type: ignore[operator]
                _make_update(text="Ты ещё помнишь меня?", user_id=601), MagicMock()
            )

            conversations_after = await _all_conversations(second_session_factory)
            assert len(conversations_after) == 1  # не создан новый диалог/пользователь
            assert conversations_after[0].id == conversation_id

            messages_final = await _messages_of(second_session_factory, conversation_id)
            assert [m.content for m in messages_final] == [
                "Привет!",
                "Ответ до перезапуска",
                "Ты ещё помнишь меня?",
                "Ответ после перезапуска",
            ]
        finally:
            await second_engine.dispose()


class TestLlmError:
    """
    Обязательный сценарий 7: LLM возвращает ошибку — user message сохранён,
    assistant message отсутствует, приложение остаётся работоспособным для
    следующего (успешного) запроса.
    """

    async def test_user_message_persisted_assistant_absent_and_next_request_succeeds(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        failing_provider = FakeLLMProvider(
            error=LLMProviderError(message="OpenRouter недоступен", user_message="Ошибка модели, попробуйте позже.")
        )
        application = _build_application(_make_process_user_message(repositories_factory, failing_provider))
        callbacks = _handler_callbacks(application)
        update = _make_update(text="Привет!", user_id=701)

        await callbacks["text"](update, MagicMock())  # type: ignore[operator]
        update.effective_message.reply_text.assert_awaited_once_with("Ошибка модели, попробуйте позже.")

        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 1
        conversation_id = conversations[0].id

        messages = await _messages_of(session_factory, conversation_id)
        assert [m.role for m in messages] == ["user"]  # assistant message отсутствует
        assert [m.content for m in messages] == ["Привет!"]

        # приложение остаётся работоспособным для следующего запроса
        working_provider = FakeLLMProvider(response=_response("Теперь всё в порядке"))
        application_ok = _build_application(_make_process_user_message(repositories_factory, working_provider))
        callbacks_ok = _handler_callbacks(application_ok)
        second_update = _make_update(text="Ты тут?", user_id=701)

        await callbacks_ok["text"](second_update, MagicMock())  # type: ignore[operator]
        second_update.effective_message.reply_text.assert_awaited_once_with("Теперь всё в порядке")

        messages_after = await _messages_of(session_factory, conversation_id)
        assert [m.role for m in messages_after] == ["user", "user", "assistant"]
        assert [m.content for m in messages_after] == ["Привет!", "Ты тут?", "Теперь всё в порядке"]


def _make_faulty_repositories_factory(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    fail_on_save_call: int,
    error: Exception,
) -> ConversationRepositoriesFactory:
    """
    Тот же принцип, что и `bootstrap/repositories.py::
    build_conversation_repositories_factory`, но `MessageRepository.save()`
    поднимает `error` на N-м вызове (считая по всем вызовам фабрики, не по
    одному открытию) — используется только сценарием 8 («ошибка базы
    данных»), чтобы проверить настоящий rollback SQLAlchemy-сессии
    (`session_scope()`), а не поведение in-memory fake-репозитория.

    `UserRepository`/`ConversationRepository` — настоящие реализации, без
    подмены: `get_or_create_by_telegram_user_id`/`get_or_create_active`
    сознательно коммитят себя автономно (S2-03/S2-04, backlog_2.md §8) —
    это не нарушение rollback-гарантии для сообщения, это задокументированное
    поведение, ниже проверяется явно.
    """
    call_count = {"n": 0}

    @asynccontextmanager
    async def _open_repositories() -> AsyncIterator[ConversationRepositories]:
        async with session_scope(session_factory) as session:
            real_messages = build_message_repository(session)

            class _FaultyMessageRepository:
                async def save(self, message: Message) -> Message:
                    call_count["n"] += 1
                    if call_count["n"] == fail_on_save_call:
                        raise error
                    return await real_messages.save(message)

                async def history(self, conversation_id: UUID) -> list[Message]:
                    return await real_messages.history(conversation_id)

                async def clear(self, conversation_id: UUID) -> int:
                    return await real_messages.clear(conversation_id)

            yield ConversationRepositories(
                users=build_user_repository(session),
                conversations=build_conversation_repository(session),
                messages=_FaultyMessageRepository(),
                profiles=build_profile_repository(session),
                memory=build_memory_repository(session),
            )

    return _open_repositories


class TestDatabaseError:
    """
    Обязательный сценарий 8: ошибка при сохранении сообщения пользователя
    откатывается, LLM не вызывается, а следующий корректный запрос
    обрабатывается успешно.
    """

    async def test_save_failure_rolls_back_skips_llm_and_next_request_succeeds(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        db_error = InfrastructureError(
            message="simulated database failure on message save",
            user_message="Не удалось обработать запрос, попробуйте позже.",
        )
        faulty_repositories_factory = _make_faulty_repositories_factory(
            session_factory, fail_on_save_call=1, error=db_error
        )
        provider = FakeLLMProvider(response=_response("Не должно быть вызвано"))
        application = _build_application(_make_process_user_message(faulty_repositories_factory, provider))
        callbacks = _handler_callbacks(application)
        update = _make_update(text="Привет!", user_id=801)

        await callbacks["text"](update, MagicMock())  # type: ignore[operator]

        update.effective_message.reply_text.assert_awaited_once_with("Не удалось обработать запрос, попробуйте позже.")
        assert provider.call_count == 0  # LLM не вызывается, если user message не сохранено

        # Сообщение не сохранено (rollback) — независимо от того, что
        # User/Conversation уже существуют (см. докстринг
        # `_make_faulty_repositories_factory`: их get_or_create коммитит
        # себя автономно, раньше неудавшегося save() сообщения).
        conversations = await _all_conversations(session_factory)
        assert len(conversations) == 1
        assert await _messages_of(session_factory, conversations[0].id) == []

        # После отката сессия/хранилище остаются пригодны для следующего,
        # уже корректного запроса того же пользователя.
        working_repositories_factory = build_conversation_repositories_factory(session_factory)
        working_provider = FakeLLMProvider(response=_response("Теперь всё сохранилось"))
        application_ok = _build_application(_make_process_user_message(working_repositories_factory, working_provider))
        callbacks_ok = _handler_callbacks(application_ok)
        second_update = _make_update(text="Повторяю запрос", user_id=801)

        await callbacks_ok["text"](second_update, MagicMock())  # type: ignore[operator]
        second_update.effective_message.reply_text.assert_awaited_once_with("Теперь всё сохранилось")

        assert working_provider.call_count == 1
        conversations_after = await _all_conversations(session_factory)
        assert len(conversations_after) == 1  # тот же диалог переиспользован, второй не создан
        messages_after = await _messages_of(session_factory, conversations_after[0].id)
        assert [m.role for m in messages_after] == ["user", "assistant"]
        assert [m.content for m in messages_after] == ["Повторяю запрос", "Теперь всё сохранилось"]
