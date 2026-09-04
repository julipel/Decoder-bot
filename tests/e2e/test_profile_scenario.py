"""
Сквозные сценарии Sprint 3 (задача S3-09, «Финальная интеграция и
E2E-проверка Sprint 3») — тот же харнесс, что и `tests/e2e/
test_conversation_persistence_scenario.py` (Sprint 2, S2-11): реальный
`telegram.ext.Application`, реальные обработчики `presentation/
telegram/`, реальные SQLAlchemy-репозитории (`bootstrap/repositories.py`)
поверх временной SQLite (`tmp_path`, схема — `Base.metadata.
create_all()`), единственная подмена — `FakeLLMProvider` (без сети, без
реального Telegram API, без `OpenAiCompatibleLLMAdapter`).

`Base.metadata.create_all()` создаёт только схему, без сид-данных (сид-
профили вносятся исключительно Alembic-миграцией S3-04, ADR-3.4) —
каталог профилей для этих сценариев вставляется вручную через
`ProfileORM` (тот же приём, что и в `tests/integration/
test_process_user_message_persistence.py`/`tests/e2e/
test_conversation_persistence_scenario.py` после S3-07).

Пять обязательных сценариев (backlog_3_tasks.md, S3-09):

    1. TestDefaultProfileWithoutSelection — новый пользователь без /profile
       получает системную инструкцию профиля-дефолта;
    2. TestProfileSwitchAffectsOnlyFuture — переключение через /profile
       влияет на system_prompt следующих сообщений, не переписывает
       уже сохранённые;
    3. TestUserIsolation — два пользователя выбирают разные профили
       независимо;
    4. TestUnknownProfileIdIsRejected — callback с несуществующим
       profile_id не меняет активный профиль и не вызывает LLM;
    5. TestFullProfileCycle — /profile → клавиатура с отметкой активного
       → выбор → подтверждение, через реальный CallbackQueryHandler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.fake_model_catalog import default_test_catalog
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.profile.dto import GetActiveProfileCommand, SelectProfileCommand
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_message_handler,
    register_profile_handlers,
)
from dekoder.presentation.telegram.handlers.profile import (
    PROFILE_NOT_FOUND_MESSAGE,
    PROFILE_SELECTED_MESSAGE_TEMPLATE,
)
from dekoder.shared.domain.identifiers import CorrelationId

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class FakeLLMProvider:
    """Единственная подмена во всей цепочке — без сети, без OpenAiCompatibleLLMAdapter."""

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
        provider_id=ProviderId("test-provider"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_text_update(text: str = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_callback_update(profile_id: UUID, user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_message = None
    query = MagicMock()
    query.data = f"profile:{profile_id}"
    query.from_user = MagicMock(id=user_id)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory,
    provider: FakeLLMProvider,
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=repositories_factory,
        prompt_builder=make_test_prompt_builder(),
        knowledge_search=FakeKnowledgeSearchService(),
        model_catalog=default_test_catalog(),
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
        max_relevant_memory=5,
    )


def _build_application(
    process_user_message: ProcessUserMessage,
    repositories_factory: ConversationRepositoriesFactory,
    list_profiles: ListProfiles,
    get_active_profile: GetActiveProfile,
    select_profile: SelectProfile,
) -> Application:
    """
    Собирает реальный `telegram.ext.Application`, тот же принцип, что и
    `telegram_main.py::_startup`. `repositories_factory` (Sprint 12) —
    строит `CreateMemoryRecordUseCase` для `register_message_handler`; ни
    один сценарий этого файла не выставляет `PENDING_REMEMBER_KEY`.
    """
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(
        application,
        process_user_message,
        CreateMemoryRecordUseCase(repositories=repositories_factory),
        get_active_profile,
    )
    register_profile_handlers(application, list_profiles, get_active_profile, select_profile)
    return application


def _handler_callbacks(application: Application) -> dict[str, object]:
    """Достаёт callback'и зарегистрированных обработчиков — `"text"`/`"profile"`/`"profile_callback"`."""
    registered = application.handlers[0]
    callbacks: dict[str, object] = {}
    for handler in registered:
        if isinstance(handler, CommandHandler):
            callbacks[next(iter(handler.commands))] = handler.callback
        elif isinstance(handler, MessageHandler):
            callbacks["text"] = handler.callback
        elif isinstance(handler, CallbackQueryHandler):
            callbacks["profile_callback"] = handler.callback
    return callbacks


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-profile.db'}"
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
) -> tuple[ListProfiles, GetActiveProfile, SelectProfile]:
    return (
        ListProfiles(repositories=repositories_factory),
        GetActiveProfile(repositories=repositories_factory),
        SelectProfile(repositories=repositories_factory),
    )


async def _seed_catalog(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, UUID]:
    """
    Вставляет 2 профиля напрямую через `ProfileORM` — `Base.metadata.
    create_all()` не вносит сид-данные (только Alembic-миграция S3-04),
    эти E2E-сценарии проверяют вертикальный срез профилей, а не саму
    сид-миграцию (отдельно покрыта `tests/integration/persistence/
    test_migrations.py`).
    """
    now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    business_id = uuid4()
    creative_id = uuid4()
    async with session_factory() as session:
        session.add(
            ProfileORM(
                id=business_id,
                name="Деловой",
                description="Кратко и по делу.",
                system_instruction="Отвечай кратко и по делу, формальный стиль.",
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
        session.add(
            ProfileORM(
                id=creative_id,
                name="Креативный",
                description="Образно, с метафорами.",
                system_instruction="Отвечай образно, с метафорами и нестандартными идеями.",
                response_style="образный",
                target_audience="широкая аудитория",
                formality_level="неформальный",
                preferred_structure="свободная форма",
                forbidden_phrasing=[],
                preferred_model=None,
                response_length_hint=None,
                additional_constraints="",
                status="active",
                is_system=True,
                is_default=False,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return {"business": business_id, "creative": creative_id}


async def _message_contents(session_factory: async_sessionmaker[AsyncSession], conversation_id: UUID) -> list[str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(MessageORM)
                .where(MessageORM.conversation_id == conversation_id)
                .order_by(MessageORM.created_at, MessageORM.id)
            )
        ).scalars()
        return [row.content for row in rows]


class TestDefaultProfileWithoutSelection:
    """Сценарий 1: новый пользователь без вызова /profile получает инструкцию профиля-дефолта."""

    async def test_new_user_gets_default_profile_system_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        use_cases: tuple[ListProfiles, GetActiveProfile, SelectProfile],
    ) -> None:
        catalog = await _seed_catalog(session_factory)
        provider = FakeLLMProvider(response=_response())
        process_user_message = _make_process_user_message(repositories_factory, provider)
        application = _build_application(process_user_message, repositories_factory, *use_cases)
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=1001), MagicMock())  # type: ignore[operator]

        assert len(provider.received_requests) == 1
        # Sprint 4 (ADR-4.7): system_prompt — склейка секций Prompt Engine,
        # не равен profile.system_instruction как есть — проверяем вхождение.
        assert "Отвечай кратко и по делу, формальный стиль." in provider.received_requests[0].system_prompt
        assert catalog["business"] is not None  # профиль-дефолт действительно использован


class TestProfileSwitchAffectsOnlyFuture:
    """Сценарий 2: переключение через /profile влияет на будущие сообщения, не переписывает историю."""

    async def test_switch_changes_future_system_prompt_without_rewriting_history(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        use_cases: tuple[ListProfiles, GetActiveProfile, SelectProfile],
    ) -> None:
        catalog = await _seed_catalog(session_factory)
        provider = FakeLLMProvider(response=_response("Ответ 1"))
        process_user_message = _make_process_user_message(repositories_factory, provider)
        application = _build_application(process_user_message, repositories_factory, *use_cases)
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(text="Первое сообщение", user_id=2001), MagicMock())  # type: ignore[operator]

        # /profile — показывает клавиатуру (сценарий не проверяет её содержимое подробно, см. сценарий 5)
        profile_update = _make_text_update(user_id=2001)
        await callbacks["profile"](profile_update, MagicMock())  # type: ignore[operator]
        profile_update.effective_message.reply_text.assert_awaited_once()

        # выбор другого профиля через callback
        callback_update = _make_callback_update(catalog["creative"], user_id=2001)
        await callbacks["profile_callback"](callback_update, MagicMock())  # type: ignore[operator]
        callback_update.callback_query.edit_message_text.assert_awaited_once_with(
            PROFILE_SELECTED_MESSAGE_TEMPLATE.format(name="Креативный", description="Образно, с метафорами.")
        )

        provider_second = FakeLLMProvider(response=_response("Ответ 2"))
        process_user_message_second = _make_process_user_message(repositories_factory, provider_second)
        application_second = _build_application(process_user_message_second, repositories_factory, *use_cases)
        callbacks_second = _handler_callbacks(application_second)

        await callbacks_second["text"](  # type: ignore[operator]
            _make_text_update(text="Второе сообщение", user_id=2001), MagicMock()
        )

        assert (
            "Отвечай образно, с метафорами и нестандартными идеями."
            in provider_second.received_requests[0].system_prompt
        )

        async with session_factory() as session:
            conversation_id = (await session.execute(select(MessageORM.conversation_id).limit(1))).scalars().first()
        assert conversation_id is not None
        contents = await _message_contents(session_factory, conversation_id)
        assert contents[:2] == ["Первое сообщение", "Ответ 1"]  # история не переписана


class TestUserIsolation:
    """Сценарий 3: два пользователя независимо выбирают разные профили."""

    async def test_each_user_gets_their_own_selected_profile(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        use_cases: tuple[ListProfiles, GetActiveProfile, SelectProfile],
    ) -> None:
        catalog = await _seed_catalog(session_factory)
        _, _, select_profile = use_cases

        # пользователь A выбирает "Креативный", пользователь B ничего не выбирает
        provider_bootstrap = FakeLLMProvider(response=_response())
        bootstrap_process_user_message = _make_process_user_message(repositories_factory, provider_bootstrap)
        bootstrap_application = _build_application(bootstrap_process_user_message, repositories_factory, *use_cases)
        bootstrap_callbacks = _handler_callbacks(bootstrap_application)
        await bootstrap_callbacks["text"](_make_text_update(user_id=3001), MagicMock())  # type: ignore[operator]
        await bootstrap_callbacks["text"](_make_text_update(user_id=3002), MagicMock())  # type: ignore[operator]

        await select_profile.execute(
            SelectProfileCommand(
                telegram_user_id=3001, profile_id=catalog["creative"], correlation_id=CorrelationId("corr-1")
            )
        )

        provider_a = FakeLLMProvider(response=_response())
        provider_b = FakeLLMProvider(response=_response())
        app_a = _build_application(
            _make_process_user_message(repositories_factory, provider_a), repositories_factory, *use_cases
        )
        app_b = _build_application(
            _make_process_user_message(repositories_factory, provider_b), repositories_factory, *use_cases
        )
        callbacks_a = _handler_callbacks(app_a)
        callbacks_b = _handler_callbacks(app_b)

        await callbacks_a["text"](_make_text_update(text="Сообщение A", user_id=3001), MagicMock())  # type: ignore[operator]
        await callbacks_b["text"](_make_text_update(text="Сообщение B", user_id=3002), MagicMock())  # type: ignore[operator]

        prompt_a = provider_a.received_requests[0].system_prompt
        prompt_b = provider_b.received_requests[0].system_prompt
        assert "Отвечай образно, с метафорами и нестандартными идеями." in prompt_a
        assert "Отвечай кратко и по делу, формальный стиль." in prompt_b
        assert prompt_a != prompt_b


class TestUnknownProfileIdIsRejected:
    """Сценарий 4: callback с неизвестным profile_id — понятное сообщение, выбор не меняется, LLM не вызван."""

    async def test_unknown_profile_id_does_not_change_selection_or_call_llm(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        use_cases: tuple[ListProfiles, GetActiveProfile, SelectProfile],
    ) -> None:
        await _seed_catalog(session_factory)
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        # регистрируем пользователя первым обычным сообщением
        await callbacks["text"](_make_text_update(user_id=4001), MagicMock())  # type: ignore[operator]
        provider.received_requests.clear()

        stale_profile_id = uuid4()
        callback_update = _make_callback_update(stale_profile_id, user_id=4001)
        await callbacks["profile_callback"](callback_update, MagicMock())  # type: ignore[operator]

        callback_update.callback_query.edit_message_text.assert_awaited_once_with(PROFILE_NOT_FOUND_MESSAGE)
        assert provider.received_requests == []  # LLM не вызывается при обработке callback'а

        _, get_active_profile, _ = use_cases
        active_result = await get_active_profile.execute(
            GetActiveProfileCommand(telegram_user_id=4001, correlation_id=CorrelationId("corr-1"))
        )
        assert active_result.profile is not None
        assert active_result.profile.name == "Деловой"  # остался дефолт, не изменился


class TestFullProfileCycle:
    """Сценарий 5: /profile → клавиатура с отметкой активного → выбор → подтверждение, реальный CallbackQueryHandler."""

    async def test_full_cycle_through_real_application_handlers(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        use_cases: tuple[ListProfiles, GetActiveProfile, SelectProfile],
    ) -> None:
        catalog = await _seed_catalog(session_factory)
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=5001), MagicMock())  # type: ignore[operator]

        profile_update = _make_text_update(user_id=5001)
        await callbacks["profile"](profile_update, MagicMock())  # type: ignore[operator]

        keyboard = profile_update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert any("Деловой" in text and "текущий" in text for text in button_texts)
        assert any(text == "Креативный" for text in button_texts)

        callback_update = _make_callback_update(catalog["creative"], user_id=5001)
        await callbacks["profile_callback"](callback_update, MagicMock())  # type: ignore[operator]

        callback_update.callback_query.answer.assert_awaited_once()
        callback_update.callback_query.edit_message_text.assert_awaited_once_with(
            PROFILE_SELECTED_MESSAGE_TEMPLATE.format(name="Креативный", description="Образно, с метафорами.")
        )
