"""
Нагрузочная проверка MVP по §18.5 «Плана реализации.md» — Sprint 10,
задача S10-04, ADR-10.4. НЕ полноценное нагрузочное тестирование
(Locust/k6/отдельная инфраструктура) — скоуп-решение №3 `backlog_10.md`:
только шесть перечисленных в плане пунктов, минимальными средствами
(`asyncio.gather`, счётчики пула SQLAlchemy).

Из шести пунктов §18.5 закрываются пять новым/переиспользуемым кодом:

    1. Несколько параллельных запросов не сериализуются —
       TestConcurrentRequestsDoNotBlockEventLoop.
    2. Event loop не блокируется одним медленным запросом — то же (общее
       время << N * delay доказывает отсутствие блокировки).
    3. Тайм-аут внешнего API — НЕ дублируется здесь, уже покрыт
       `tests/integration/llm/test_openai_compatible_adapter.py::
       test_timeout_raises_llm_provider_error` (см. таблицу трассируемости
       Спринт 10_отчёт.md).
    4. Корректное освобождение соединений с БД —
       TestConnectionPoolIsReleased (успешный и сбойный путь).
    5. Ограничение повторных запросов — НЕ тестируется новым кодом
       (скоуп-решение №4 `backlog_10.md`: в коде проекта такой функции нет
       и не планировалось ни в одном из этапов 1–11; трактуется как
       graceful-обработка HTTP 429 от AI-провайдера, уже покрыто
       `test_openai_compatible_adapter.py::test_rate_limit_raises_llm_provider_error`).
    6. Поведение при длинном ответе — НЕ дублируется, уже покрыто
       `tests/unit/presentation/telegram/test_mapper.py::split_message`.

Дополнительно (сверх буквальных шести пунктов, но напрямую связано с
«несколько параллельных запросов»): TestConcurrentProviderErrorsDoNotCrashApp
— конкурентные ошибки провайдера не должны ронять приложение целиком
(каждый пользователь получает штатное сообщение об ошибке).

`_DelayedFakeLLMProvider` — ЛОКАЛЬНАЯ заглушка только этого файла (ADR-10.4,
Архитектурные заметки: не выносится в `tests/support/`, не переиспользуется
другими per-file `FakeLLMProvider` в других e2e-файлах). Тайминг-пороги —
с запасом (`< 2 * delay`, не `1.1 * delay`) — не хрупкие к дрожанию
CI-раннера (ADR-10.4, «Недостатки»).

`src/dekoder/**`, включая `infrastructure/persistence/engine.py`, не
меняется — тест только читает `engine.pool.checkedout()` через стандартный
SQLAlchemy `Pool` API.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, MessageHandler
from tests.e2e.test_conversation_persistence_scenario import _make_faulty_repositories_factory
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.fake_model_catalog import default_test_catalog
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.presentation.telegram.bot import build_telegram_application, register_message_handler
from dekoder.shared.errors import InfrastructureError, LLMProviderError

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class _DelayedFakeLLMProvider:
    """
    Локальная заглушка `LLMProvider` только для этого файла (ADR-10.4) —
    `await asyncio.sleep(delay)` перед возвратом ответа/поднятием ошибки,
    имитирует медленный сетевой вызов реального провайдера под нагрузкой.
    """

    def __init__(self, *, delay: float, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._delay = delay
        self._response = response
        self._error = error
        self.call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _response(text: str = "Ответ") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("test-provider"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_process_user_message(
    repositories_factory: ConversationRepositoriesFactory,
    provider: _DelayedFakeLLMProvider,
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


def _build_application(process_user_message: ProcessUserMessage) -> Application:
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(application, process_user_message)
    return application


def _text_handler_callback(application: Application) -> object:
    """Callback уже зарегистрированного `MessageHandler` — по образцу `_handler_callbacks` (test_conversation_*)."""
    for handler in application.handlers[0]:
        if isinstance(handler, MessageHandler):
            return handler.callback
    raise AssertionError("MessageHandler не зарегистрирован")


def _make_update(text: str, user_id: int) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'concurrency.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def repositories_factory(session_factory: async_sessionmaker[AsyncSession]) -> ConversationRepositoriesFactory:
    return build_conversation_repositories_factory(session_factory)


@pytest.fixture(autouse=True)
async def _default_profile(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """`ProcessUserMessage` требует хотя бы один активный профиль с `is_default=True` (см. test_conversation_*)."""
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


class TestConcurrentRequestsDoNotBlockEventLoop:
    """
    §18.5, пункты 1-2: несколько параллельных запросов не сериализуются,
    event loop не блокируется одним медленным вызовом провайдера (AC-1).
    """

    async def test_n_parallel_requests_complete_well_under_n_times_delay(
        self, repositories_factory: ConversationRepositoriesFactory
    ) -> None:
        delay = 0.5
        n = 5
        provider = _DelayedFakeLLMProvider(delay=delay, response=_response())
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callback = _text_handler_callback(application)
        updates = [_make_update(f"Сообщение {i}", user_id=1000 + i) for i in range(n)]

        started_at = time.monotonic()
        await asyncio.gather(*(callback(update, MagicMock()) for update in updates))  # type: ignore[operator]
        elapsed = time.monotonic() - started_at

        assert provider.call_count == n
        # С запасом (ADR-10.4): последовательное выполнение заняло бы >= n * delay (1.0s);
        # порог 2 * delay (0.4s) не флаки на медленном CI-раннере, но однозначно доказывает параллелизм.
        assert elapsed < 2 * delay
        for update in updates:
            update.effective_message.reply_text.assert_awaited_once_with("Ответ")


class TestConnectionPoolIsReleased:
    """§18.5, пункт 4: корректное освобождение соединений с БД — успешный и сбойный путь (AC-2)."""

    async def test_pool_has_zero_checked_out_connections_after_a_batch_of_successful_requests(
        self, engine: AsyncEngine, repositories_factory: ConversationRepositoriesFactory
    ) -> None:
        provider = _DelayedFakeLLMProvider(delay=0.01, response=_response())
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callback = _text_handler_callback(application)
        updates = [_make_update(f"Запрос {i}", user_id=2000 + i) for i in range(5)]

        await asyncio.gather(*(callback(update, MagicMock()) for update in updates))  # type: ignore[operator]

        assert engine.pool.checkedout() == 0

    async def test_pool_has_zero_checked_out_connections_after_a_failing_request(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """
        Переиспользует `_make_faulty_repositories_factory`
        (`tests/e2e/test_conversation_persistence_scenario.py`) — не
        дублирует реализацию сбойного репозитория (ADR-10.4).
        """
        db_error = InfrastructureError(
            message="simulated database failure on message save",
            user_message="Не удалось обработать запрос, попробуйте позже.",
        )
        faulty_repositories_factory = _make_faulty_repositories_factory(
            session_factory, fail_on_save_call=1, error=db_error
        )
        provider = _DelayedFakeLLMProvider(delay=0.01, response=_response())
        application = _build_application(_make_process_user_message(faulty_repositories_factory, provider))
        callback = _text_handler_callback(application)
        update = _make_update("Сбойный запрос", user_id=3000)

        await callback(update, MagicMock())  # type: ignore[operator]

        update.effective_message.reply_text.assert_awaited_once_with("Не удалось обработать запрос, попробуйте позже.")
        assert provider.call_count == 0  # LLM не вызывается, если user message не сохранено
        assert engine.pool.checkedout() == 0


class TestConcurrentProviderErrorsDoNotCrashApp:
    """Конкурентные ошибки провайдера не роняют приложение — каждый пользователь получает штатный ответ (AC-3)."""

    async def test_each_user_gets_a_normal_error_reply_and_no_exception_propagates(
        self, repositories_factory: ConversationRepositoriesFactory
    ) -> None:
        n = 5
        provider = _DelayedFakeLLMProvider(
            delay=0.05,
            error=LLMProviderError(message="LLM провайдер недоступен", user_message="Ошибка модели, попробуйте позже."),
        )
        application = _build_application(_make_process_user_message(repositories_factory, provider))
        callback = _text_handler_callback(application)
        updates = [_make_update(f"Вопрос {i}", user_id=4000 + i) for i in range(n)]

        results = await asyncio.gather(
            *(callback(update, MagicMock()) for update in updates),  # type: ignore[operator]
            return_exceptions=True,
        )

        assert all(not isinstance(result, BaseException) for result in results)
        assert provider.call_count == n
        for update in updates:
            update.effective_message.reply_text.assert_awaited_once_with("Ошибка модели, попробуйте позже.")
