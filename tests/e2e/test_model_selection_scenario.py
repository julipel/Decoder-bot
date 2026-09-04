"""
Сквозные сценарии Sprint 7 (задача S7-08, «Финальная интеграция и
E2E-проверка Sprint 7») — тот же харнесс, что и `tests/e2e/
test_profile_scenario.py`: реальный `telegram.ext.Application`, реальные
обработчики `presentation/telegram/`, реальные SQLAlchemy-репозитории
(`bootstrap/repositories.py`) поверх временной SQLite (`tmp_path`, схема
— `Base.metadata.create_all()`), реальный `ConfigModelCatalogRepository`
— единственная подмена, как и в остальных e2e Sprint 1-6, `FakeLLMProvider`
(без сети, без реального Telegram API, без `OpenAiCompatibleLLMAdapter`):
детерминированная проверка `LLMRequest.model_id`/`temperature`/`max_tokens`,
не реальный вызов LLM — тот же приём, что S5-08 проверял
`PromptBuildResult.system_prompt`.

Боевой каталог (см. `infrastructure/model_catalog/catalog.json`) читается
как есть для AVAILABLE-моделей: `openai/gpt-4o-mini` (умолчание),
`anthropic/claude-sonnet-5` (другие `temperature`/`max_tokens`).

Sprint 13: UNAVAILABLE-модель для сценариев отката/отклонения (AC-2/AC-3)
больше не хранится постоянно в боевом каталоге — раньше эту роль играла
`anthropic/claude-3-haiku`, но она же видна пользователю в `/model` как
устаревшая недоступная запись (по требованию ADR-7.9 «список не портится,
запись видна»), что и было тем самым «мусором» в каталоге; убрана оттуда
по явному запросу пользователя. Вместо этого фикстура `model_catalog`
берёт боевые AVAILABLE-записи как есть и добавляет одну синтетическую
UNAVAILABLE-запись (`_UNAVAILABLE_MODEL_ID`) только в тестовую копию
файла (`tmp_path`) — прод-каталог ею не нагружается, а сценарии отката/
отклонения по-прежнему проверяются через реальный `ConfigModelCatalogRepository`,
не через полностью придуманный каталог.

Четыре сценария (backlog_7_tasks.md, S7-08):

    1. TestModelSelectionAffectsGeneration — /model → выбор доступной
       модели → обычное сообщение → LLMRequest.model_id/temperature/
       max_tokens соответствуют выбору (AC-1);
    2. TestFallbackWhenSelectedModelIsUnavailable — персональный выбор
       указывает на модель, впоследствии помеченную UNAVAILABLE в
       каталоге (симулируется прямой записью в `user_active_models`,
       минуя `SelectModel`, — так же, как реальный каталог мог измениться
       после того, как выбор был сделан) — сообщение всё равно
       генерируется моделью по умолчанию, лог отката записан (AC-2);
    3. TestUserIsolation — два пользователя выбирают разные модели,
       выбор одного не влияет на генерацию для другого;
    4. TestFullModelSelectionCycle — /model → клавиатура с отметкой
       активной модели → выбор через callback → подтверждение с
       обновлённым списком, через реальный CallbackQueryHandler; попытка
       выбрать UNAVAILABLE-модель отклоняется, видна пользователю, список
       не портится (AC-3, ADR-7.9).
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
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.model_catalog.dto import GetSelectedModelCommand, SelectModelCommand
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.model_catalog.config_repository import DEFAULT_CATALOG_PATH, ConfigModelCatalogRepository
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.sqlalchemy_model_selection_repository import (
    SQLAlchemyModelSelectionRepository,
)
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_message_handler,
    register_model_handlers,
)
from dekoder.presentation.telegram.handlers.model import MODEL_SELECTED_MESSAGE_TEMPLATE
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.logging import clear_request_context, configure_logging

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет

# Значения из боевого сид-каталога (infrastructure/model_catalog/catalog.json) — см. докстринг модуля.
_DEFAULT_MODEL_ID = ModelId("openai/gpt-4o-mini")
_SONNET_MODEL_ID = ModelId("anthropic/claude-sonnet-5")

# Синтетическая запись (Sprint 13) — существует только в тестовой копии
# каталога (см. фикстуру model_catalog), не в боевом catalog.json.
_UNAVAILABLE_MODEL_ID = ModelId("test-provider/discontinued-model")
_UNAVAILABLE_MODEL_DISPLAY_NAME = "Устаревшая тестовая модель"
_UNAVAILABLE_MODEL_CATALOG_ENTRY = {
    "model_id": _UNAVAILABLE_MODEL_ID.value,
    "display_name": _UNAVAILABLE_MODEL_DISPLAY_NAME,
    "provider": "other",
    "context_window": 8000,
    "capabilities": ["text"],
    "price_tier": "low",
    "availability": "unavailable",
    "recommended_for": [],
    "default_generation_settings": {"temperature": 0.7, "max_tokens": 512},
}


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
        model_id=_DEFAULT_MODEL_ID,
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


def _make_callback_update(model_id: ModelId, user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_message = None
    query = MagicMock()
    query.data = f"model:{model_id.value}"
    query.from_user = MagicMock(id=user_id)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory,
    provider: FakeLLMProvider,
    model_catalog: ModelCatalogRepository,
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=repositories_factory,
        prompt_builder=make_test_prompt_builder(),
        knowledge_search=FakeKnowledgeSearchService(),
        model_catalog=model_catalog,
        default_model=_DEFAULT_MODEL_ID,
        temperature=0.1,
        max_tokens=64,
        max_relevant_memory=5,
    )


def _build_application(
    process_user_message: ProcessUserMessage,
    repositories_factory: ConversationRepositoriesFactory,
    list_available_models: ListAvailableModels,
    get_selected_model: GetSelectedModel,
    select_model: SelectModel,
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
        GetActiveProfile(repositories=repositories_factory),
    )
    register_model_handlers(application, list_available_models, get_selected_model, select_model)
    return application


def _handler_callbacks(application: Application) -> dict[str, object]:
    """Достаёт callback'и зарегистрированных обработчиков — `"text"`/`"model"`/`"model_callback"`."""
    registered = application.handlers[0]
    callbacks: dict[str, object] = {}
    for handler in registered:
        if isinstance(handler, CommandHandler):
            callbacks[next(iter(handler.commands))] = handler.callback
        elif isinstance(handler, MessageHandler):
            callbacks["text"] = handler.callback
        elif isinstance(handler, CallbackQueryHandler):
            callbacks["model_callback"] = handler.callback
    return callbacks


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-model-selection.db'}"
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
def model_catalog(tmp_path: Path) -> ModelCatalogRepository:
    """
    Боевые AVAILABLE-записи (`infrastructure/model_catalog/catalog.json`,
    та же конфигурация, что грузит `bootstrap/container.py`) + одна
    синтетическая UNAVAILABLE-запись, дописанная только в эту временную
    копию файла (Sprint 13, см. докстринг модуля) — прод-каталог не несёт
    постоянной недоступной записи ради покрытия отката/отклонения.
    """
    real_models = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    fixture_path = tmp_path / "model_catalog.json"
    fixture_path.write_text(json.dumps([*real_models, _UNAVAILABLE_MODEL_CATALOG_ENTRY]), encoding="utf-8")
    return ConfigModelCatalogRepository(catalog_path=fixture_path)


@pytest.fixture
def use_cases(
    repositories_factory: ConversationRepositoriesFactory,
    model_catalog: ModelCatalogRepository,
) -> tuple[ListAvailableModels, GetSelectedModel, SelectModel]:
    return (
        ListAvailableModels(repositories=repositories_factory, model_catalog=model_catalog),
        GetSelectedModel(repositories=repositories_factory, model_catalog=model_catalog),
        SelectModel(repositories=repositories_factory, model_catalog=model_catalog),
    )


@pytest.fixture(autouse=True)
async def _seed_default_profile(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """
    `Base.metadata.create_all()` не вносит сид-данные (профили — только
    Alembic-миграция S3-04) — эти сценарии проверяют каталог моделей, не
    Prompt Engine/профили, поэтому вставляется единственный
    is_default=True профиль напрямую через `ProfileORM` (тот же приём,
    что `tests/e2e/test_profile_scenario.py::_seed_catalog`), достаточный
    для того, чтобы `ProcessUserMessage._save_user_message` (тем же
    вызовом читающий `profiles.get_active_profile`) не падал на пустом
    каталоге.
    """
    now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    async with session_factory() as session:
        session.add(
            ProfileORM(
                id=uuid4(),
                name="Тестовый",
                description="Профиль по умолчанию для e2e-сценариев каталога моделей.",
                system_instruction="Отвечай кратко и по делу.",
                response_style="нейтральный",
                target_audience="широкая аудитория",
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


async def _directly_persist_selection(
    session_factory: async_sessionmaker[AsyncSession], user_id: object, model_id: ModelId
) -> None:
    """
    Записывает персональный выбор напрямую через `SQLAlchemyModelSelectionRepository.select()`,
    в обход `SelectModel` (который отклонил бы `UNAVAILABLE`-модель,
    ADR-7.9) — симулирует «пользователь выбрал модель, когда она ещё была
    доступна, каталог обновился уже после этого» (ADR-7.7 AC-3/S7-08 AC-2).
    """
    async with session_factory() as session:
        repository = SQLAlchemyModelSelectionRepository(session)
        await repository.select(user_id, model_id)  # type: ignore[arg-type]


class TestModelSelectionAffectsGeneration:
    """AC-1 (S7-08): выбор модели → генерация с этой моделью, включая temperature/max_tokens из каталога."""

    async def test_selected_model_and_its_generation_settings_reach_the_llm_request(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        _, _, select_model = use_cases
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        # регистрируем пользователя обычным сообщением, затем выбираем модель через /model
        await callbacks["text"](_make_text_update(user_id=9001), MagicMock())  # type: ignore[operator]
        provider.received_requests.clear()

        await select_model.execute(
            SelectModelCommand(telegram_user_id=9001, model_id=_SONNET_MODEL_ID, correlation_id=CorrelationId("corr-1"))
        )

        await callbacks["text"](_make_text_update(text="Как дела?", user_id=9001), MagicMock())  # type: ignore[operator]

        assert len(provider.received_requests) == 1
        request = provider.received_requests[0]
        sonnet = model_catalog.get(_SONNET_MODEL_ID)
        assert sonnet is not None
        assert request.model_id == _SONNET_MODEL_ID
        assert request.temperature == sonnet.default_generation_settings.temperature
        assert request.max_tokens == sonnet.default_generation_settings.max_tokens
        # Настройки каталога вытеснили Settings.llm.temperature/max_tokens,
        # переданные ProcessUserMessage конструктором (0.1/64, см.
        # `_make_process_user_message`) — не совпадают случайно.
        assert request.temperature != 0.1
        assert request.max_tokens != 64

    async def test_without_selection_uses_default_model_and_its_own_settings(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        """Регрессия: пользователь без выбора — поведение Sprint 1-6 (умолчание) не изменилось."""
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=9002), MagicMock())  # type: ignore[operator]

        request = provider.received_requests[0]
        default_model = model_catalog.get(_DEFAULT_MODEL_ID)
        assert default_model is not None
        assert request.model_id == _DEFAULT_MODEL_ID
        assert request.temperature == default_model.default_generation_settings.temperature
        assert request.max_tokens == default_model.default_generation_settings.max_tokens


class TestFallbackWhenSelectedModelIsUnavailable:
    """AC-2 (S7-08): персональный выбор указывает на UNAVAILABLE-модель — откат на умолчание, лог записан."""

    async def test_generation_falls_back_to_default_model_and_logs_the_fallback(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        clear_request_context()
        configure_logging(environment="test")
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=9101), MagicMock())  # type: ignore[operator]
        provider.received_requests.clear()

        async with repositories_factory() as repositories:
            user = await repositories.users.get_by_telegram_user_id(9101)
        assert user is not None
        await _directly_persist_selection(session_factory, user.id, _UNAVAILABLE_MODEL_ID)

        await callbacks["text"](_make_text_update(text="Ещё сообщение", user_id=9101), MagicMock())  # type: ignore[operator]

        assert len(provider.received_requests) == 1
        request = provider.received_requests[0]
        assert request.model_id == _DEFAULT_MODEL_ID

        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        fallback_entries = [line for line in log_lines if line.get("event") == "model_selection_fallback"]
        assert len(fallback_entries) == 1
        assert fallback_entries[0]["requested_model_id"] == _UNAVAILABLE_MODEL_ID.value
        assert fallback_entries[0]["fallback_model_id"] == _DEFAULT_MODEL_ID.value
        assert fallback_entries[0]["level"] == "warning"
        clear_request_context()

    async def test_response_is_still_generated_successfully(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        provider = FakeLLMProvider(response=_response("Ответ несмотря на откат"))
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        update = _make_text_update(user_id=9102)
        await callbacks["text"](update, MagicMock())  # type: ignore[operator]
        async with repositories_factory() as repositories:
            user = await repositories.users.get_by_telegram_user_id(9102)
        assert user is not None
        await _directly_persist_selection(session_factory, user.id, _UNAVAILABLE_MODEL_ID)

        second_update = _make_text_update(text="Работает?", user_id=9102)
        await callbacks["text"](second_update, MagicMock())  # type: ignore[operator]

        second_update.effective_message.reply_text.assert_awaited_with("Ответ несмотря на откат")


class TestUserIsolation:
    """Выбор одного пользователя не влияет на генерацию для другого."""

    async def test_each_user_gets_their_own_selected_model(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        _, _, select_model = use_cases
        bootstrap_provider = FakeLLMProvider(response=_response())
        bootstrap_app = _build_application(
            _make_process_user_message(repositories_factory, bootstrap_provider, model_catalog),
            repositories_factory,
            *use_cases,
        )
        bootstrap_callbacks = _handler_callbacks(bootstrap_app)
        await bootstrap_callbacks["text"](_make_text_update(user_id=9201), MagicMock())  # type: ignore[operator]
        await bootstrap_callbacks["text"](_make_text_update(user_id=9202), MagicMock())  # type: ignore[operator]

        await select_model.execute(
            SelectModelCommand(telegram_user_id=9201, model_id=_SONNET_MODEL_ID, correlation_id=CorrelationId("corr-1"))
        )
        # пользователь 9202 ничего не выбирает — остаётся на умолчании

        provider_a = FakeLLMProvider(response=_response())
        provider_b = FakeLLMProvider(response=_response())
        app_a = _build_application(
            _make_process_user_message(repositories_factory, provider_a, model_catalog),
            repositories_factory,
            *use_cases,
        )
        app_b = _build_application(
            _make_process_user_message(repositories_factory, provider_b, model_catalog),
            repositories_factory,
            *use_cases,
        )
        callbacks_a = _handler_callbacks(app_a)
        callbacks_b = _handler_callbacks(app_b)

        await callbacks_a["text"](_make_text_update(text="Сообщение A", user_id=9201), MagicMock())  # type: ignore[operator]
        await callbacks_b["text"](_make_text_update(text="Сообщение B", user_id=9202), MagicMock())  # type: ignore[operator]

        assert provider_a.received_requests[0].model_id == _SONNET_MODEL_ID
        assert provider_b.received_requests[0].model_id == _DEFAULT_MODEL_ID


class TestFullModelSelectionCycle:
    """AC-3 (S7-08)/ADR-7.9: /model → клавиатура → выбор через callback → подтверждение; UNAVAILABLE отклонена."""

    async def test_full_cycle_through_real_application_handlers(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=9301), MagicMock())  # type: ignore[operator]

        model_update = _make_text_update(user_id=9301)
        await callbacks["model"](model_update, MagicMock())  # type: ignore[operator]

        keyboard = model_update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert any(_UNAVAILABLE_MODEL_DISPLAY_NAME in text and "недоступна" in text for text in button_texts)

        callback_update = _make_callback_update(_SONNET_MODEL_ID, user_id=9301)
        await callbacks["model_callback"](callback_update, MagicMock())  # type: ignore[operator]

        callback_update.callback_query.answer.assert_awaited_once_with()
        callback_update.callback_query.edit_message_text.assert_awaited_once()
        assert callback_update.callback_query.edit_message_text.call_args.args[
            0
        ] == MODEL_SELECTED_MESSAGE_TEMPLATE.format(name="Claude Sonnet 5")

    async def test_selecting_unavailable_model_is_rejected_and_visible_to_the_user(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        model_catalog: ModelCatalogRepository,
        use_cases: tuple[ListAvailableModels, GetSelectedModel, SelectModel],
    ) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(
            _make_process_user_message(repositories_factory, provider, model_catalog), repositories_factory, *use_cases
        )
        callbacks = _handler_callbacks(application)

        await callbacks["text"](_make_text_update(user_id=9302), MagicMock())  # type: ignore[operator]

        callback_update = _make_callback_update(_UNAVAILABLE_MODEL_ID, user_id=9302)
        await callbacks["model_callback"](callback_update, MagicMock())  # type: ignore[operator]

        # Список не портится — сообщение НЕ редактируется, пользователь видит только alert (ADR-7.9).
        callback_update.callback_query.edit_message_text.assert_not_awaited()
        assert callback_update.callback_query.answer.call_args.kwargs.get("show_alert") is True

        _, get_selected_model, _ = use_cases
        selected = await get_selected_model.execute(
            GetSelectedModelCommand(telegram_user_id=9302, correlation_id=CorrelationId("corr-1"))
        )
        assert selected.model is None  # выбор не изменился (изначально не был сделан)
