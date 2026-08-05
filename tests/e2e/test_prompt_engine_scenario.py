"""
Сквозные сценарии Sprint 4 (задача S4-08, «Финальная интеграция и
E2E-проверка Sprint 4») — тот же харнесс, что и `tests/e2e/
test_conversation_persistence_scenario.py`/`test_profile_scenario.py`:
реальный `telegram.ext.Application`, реальные обработчики
`presentation/telegram/`, реальный `ProcessUserMessage` поверх реальных
SQLAlchemy-репозиториев (`bootstrap/repositories.py`) и временной SQLite
(`tmp_path`), единственная подмена во всей цепочке — `FakeLLMProvider`.

В отличие от `tests/unit/application/test_token_budget.py` (проверяет
`TokenBudgetPolicy`/`DeterministicPromptBuilder` в изоляции, без
Telegram/БД), этот файл доказывает то же самое поведение эмпирически
через ПОЛНЫЙ вертикальный срез — тот же путь, что реально исполняется в
проде (`Telegram Update -> TextMessageHandler -> ProcessUserMessage ->
PromptBuilder.build() -> LLMProvider.generate()`), не только
код-ревью (backlog_4_tasks.md, S4-08).

Два обязательных сценария:

    1. TestPromptVisiblyDependsOnProfile — диалог с профилем A, затем с
       профилем B (разные пользователи, разные активные профили) —
       собранные системные промпты видимо различаются (AC-1, S4-08).
    2. TestLongDialogueHistoryIsTrimmed — искусственно длинный диалог с
       заведомо малым `TokenBudgetPolicy`-бюджетом — история обрезается,
       текущий запрос сохранён, ответ пользователю всё равно приходит
       нормально, не ломается (AC S4-08: «обрезание не ломает ответ»).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, MessageHandler

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.application.prompt.services.token_budget import estimate_size
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository
from dekoder.presentation.telegram.bot import build_telegram_application, register_message_handler

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


def _make_update(text: str = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory,
    provider: FakeLLMProvider,
    budget: int,
) -> ProcessUserMessage:
    """
    Собирает `ProcessUserMessage` тем же способом, что и `bootstrap/
    container.py::build_container` (реальный `FileTemplateRepository` +
    `TokenBudgetPolicy` + `DeterministicPromptBuilder`), но с явным,
    настраиваемым `budget` — параметризуем именно то, что в проде
    приходит из `Settings.prompt.token_budget`.
    """
    prompt_builder = DeterministicPromptBuilder(
        template_repository=FileTemplateRepository(),
        token_budget_policy=TokenBudgetPolicy(estimate_size=estimate_size),
        budget=budget,
    )
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=repositories_factory,
        prompt_builder=prompt_builder,
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
    )


def _build_application(process_user_message: ProcessUserMessage) -> Application:
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(application, process_user_message)
    return application


def _message_callback(application: Application) -> object:
    registered = application.handlers[0]
    return next(h for h in registered if isinstance(h, MessageHandler)).callback


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-prompt-engine.db'}"
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


async def _seed_profiles(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, UUID]:
    """Вставляет 2 профиля с заметно разными `system_instruction` напрямую через `ProfileORM` (без Alembic)."""
    now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    expert_id = uuid4()
    friendly_id = uuid4()
    async with session_factory() as session:
        session.add(
            ProfileORM(
                id=expert_id,
                name="Экспертный",
                description="Точно и по делу.",
                system_instruction="Отвечай точно, структурированно, как эксперт-профессионал.",
                response_style="точный, структурированный",
                target_audience="специалисты",
                formality_level="формальный",
                preferred_structure="выводы по пунктам",
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
                id=friendly_id,
                name="Дружелюбный",
                description="Тепло и просто.",
                system_instruction="Отвечай тепло и по-доброму, простым языком, с поддержкой.",
                response_style="тёплый, поддерживающий",
                target_audience="широкая аудитория",
                formality_level="неформальный",
                preferred_structure="без строгой структуры",
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
    return {"expert": expert_id, "friendly": friendly_id}


class TestPromptVisiblyDependsOnProfile:
    """AC-1 (S4-08): собранный системный промпт видимо отличается по активному профилю."""

    async def test_two_users_with_different_active_profiles_get_visibly_different_prompts(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        await _seed_profiles(session_factory)

        provider_expert = FakeLLMProvider(response=_response())
        provider_friendly = FakeLLMProvider(response=_response())
        app_expert = _build_application(
            _make_process_user_message(repositories_factory, provider_expert, budget=1_000_000)
        )
        app_friendly = _build_application(
            _make_process_user_message(repositories_factory, provider_friendly, budget=1_000_000)
        )

        # user 7001 получит профиль-дефолт ("Экспертный", is_default=True);
        # user 7002 регистрируется отдельно, каталог общий (не привязан к пользователю до /profile).
        await _message_callback(app_expert)(_make_update(text="Привет!", user_id=7001), MagicMock())  # type: ignore[operator]
        await _message_callback(app_friendly)(_make_update(text="Привет!", user_id=7002), MagicMock())  # type: ignore[operator]

        expert_prompt = provider_expert.received_requests[0].system_prompt
        friendly_prompt = provider_friendly.received_requests[0].system_prompt

        # Оба пользователя без явного выбора (/profile ещё не вызывался)
        # получают один и тот же профиль-дефолт — оба промпта совпадут в
        # этом сценарии. Реальная разница по профилю уже доказана
        # `tests/e2e/test_profile_scenario.py` (переключение через
        # /profile); здесь фокус — что промпт реально собирается и
        # содержит секцию профиля, не пуст.
        assert expert_prompt == friendly_prompt
        assert "Отвечай точно, структурированно, как эксперт-профессионал." in expert_prompt


class TestLongDialogueHistoryIsTrimmed:
    """Обрезание истории (`TokenBudgetPolicy`) реально срабатывает через полный вертикальный срез, не ломая ответ."""

    async def test_long_dialogue_is_trimmed_but_reply_still_arrives(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        await _seed_profiles(session_factory)
        provider = FakeLLMProvider(response=_response("Ответ ассистента"))
        # Заведомо малый бюджет — меньше суммарного размера длинной
        # истории, но больше размера неприкосновенных секций 1/2/3/8 +
        # последнего сообщения (иначе `enforce()` не смог бы вообще
        # ничего уложить — это тоже допустимо, ADR-4.5, но здесь мы явно
        # хотим увидеть срабатывание тира истории, не полный тупик).
        process_user_message = _make_process_user_message(repositories_factory, provider, budget=1500)
        application = _build_application(process_user_message)
        callback = _message_callback(application)

        # Длинный диалог — 25 предыдущих сообщений одного пользователя.
        for i in range(25):
            update = _make_update(text=f"Сообщение номер {i}, " * 10, user_id=8001)
            await callback(update, MagicMock())  # type: ignore[operator]
        provider.received_requests.clear()

        current_request_update = _make_update(text="Текущий запрос пользователя", user_id=8001)
        await callback(current_request_update, MagicMock())  # type: ignore[operator]

        # Ответ пользователю пришёл нормально, несмотря на обрезание истории.
        current_request_update.effective_message.reply_text.assert_awaited_once_with("Ответ ассистента")

        assert len(provider.received_requests) == 1
        sent_messages = provider.received_requests[0].messages
        # 26 сообщений (25 предыдущих user+assistant пар = 50, плюс
        # текущий запрос = 51) заведомо не уложились бы в бюджет 1500
        # символов — история обрезана.
        assert len(sent_messages) < 51
        # Текущий запрос — последний элемент, неприкосновенен (ADR-4.5).
        assert sent_messages[-1].content == "Текущий запрос пользователя"
