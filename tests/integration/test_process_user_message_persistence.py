"""
Интеграционный тест полного persistence-потока `ProcessUserMessage`
(Sprint 2, задача S2-06) — реальные SQLAlchemy-репозитории поверх
временной SQLite (`tmp_path`, схема через `Base.metadata.create_all()`,
единственное допустимое исключение для тестового окружения,
backlog_2.md §3), fake `LLMProvider` (без сетевого вызова, без
`OpenRouterLLMAdapter`).

Проверяет ровно то, что требует backlog_2_tasks.md (S2-06, «Добавь
интеграционный тест полного persistence-потока»):
- обработка первого сообщения -> 2 записи messages (user, assistant);
- обработка второго сообщения в том же диалоге -> 4 записи, порядок
  ролей user/assistant/user/assistant;
- один и тот же conversation_id для обоих сообщений;
- LLM реально получил историю прошлых сообщений (через `FakeLLMProvider.
  received_requests`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.fake_model_catalog import default_test_catalog
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse, ProcessUserMessageCommand
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.domain.identifiers import CorrelationId


class FakeLLMProvider:
    """Fake без сетевого вызова — реальный OpenRouterLLMAdapter сюда не подключается."""

    def __init__(self) -> None:
        self.received_requests: list[LLMRequest] = []
        self._reply_counter = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        self._reply_counter += 1
        return LLMResponse(
            text=f"Ответ {self._reply_counter}",
            provider_id=ProviderId("openrouter"),
            model_id=request.model_id,
            input_tokens=10,
            output_tokens=5,
            duration_ms=1.0,
        )


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'process-user-message.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


@pytest.fixture(autouse=True)
async def _default_profile(session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
    """
    `Base.metadata.create_all()` создаёт только схему, без сид-данных
    (сид-профили вносятся исключительно Alembic-миграцией S3-04, ADR-3.4)
    — с задачи S3-07 `ProcessUserMessage` требует хотя бы один активный
    профиль с `is_default=True` (иначе `get_active_profile` поднимает
    `InfrastructureError`), поэтому тестовое окружение вставляет один
    профиль напрямую через `ProfileORM`, как и остальные интеграционные
    тесты этого файла делают со схемой.
    """
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


def _make_use_case(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    provider: FakeLLMProvider,
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=build_conversation_repositories_factory(session_factory),
        prompt_builder=make_test_prompt_builder(),
        knowledge_search=FakeKnowledgeSearchService(),
        model_catalog=default_test_catalog(),
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
        max_relevant_memory=5,
    )


class TestFullPersistenceFlow:
    async def test_first_message_creates_two_messages(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        provider = FakeLLMProvider()
        use_case = _make_use_case(session_factory, provider)

        result = await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=555,
                message_text="Привет!",
                correlation_id=CorrelationId("corr-1"),
            )
        )

        async with session_factory() as session:
            rows = (
                (await session.execute(select(MessageORM).order_by(MessageORM.created_at, MessageORM.id)))
                .scalars()
                .all()
            )

        assert len(rows) == 2
        assert [row.role for row in rows] == ["user", "assistant"]
        assert all(row.conversation_id == result.conversation_id for row in rows)

    async def test_second_message_in_same_conversation_reaches_four_messages_in_role_order(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        provider = FakeLLMProvider()
        use_case = _make_use_case(session_factory, provider)

        first_result = await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=777,
                message_text="Сообщение 1",
                correlation_id=CorrelationId("corr-1"),
            )
        )
        second_result = await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=777,
                message_text="Сообщение 2",
                correlation_id=CorrelationId("corr-2"),
            )
        )

        assert first_result.conversation_id == second_result.conversation_id

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(MessageORM)
                        .where(MessageORM.conversation_id == first_result.conversation_id)
                        .order_by(MessageORM.created_at, MessageORM.id)
                    )
                )
                .scalars()
                .all()
            )

        assert len(rows) == 4
        assert [row.role for row in rows] == ["user", "assistant", "user", "assistant"]
        assert {row.conversation_id for row in rows} == {first_result.conversation_id}

    async def test_llm_receives_history_of_past_messages_on_second_call(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        provider = FakeLLMProvider()
        use_case = _make_use_case(session_factory, provider)

        await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=888,
                message_text="Сообщение 1",
                correlation_id=CorrelationId("corr-1"),
            )
        )
        await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=888,
                message_text="Сообщение 2",
                correlation_id=CorrelationId("corr-2"),
            )
        )

        assert len(provider.received_requests) == 2
        first_request_contents = [m.content for m in provider.received_requests[0].messages]
        assert first_request_contents == ["Сообщение 1"]

        second_request_contents = [m.content for m in provider.received_requests[1].messages]
        assert second_request_contents == ["Сообщение 1", "Ответ 1", "Сообщение 2"]


class TestProfileSwitchAffectsOnlyFutureMessages:
    """
    Sprint 3, задача S3-07, AC-2: переключение активного профиля влияет
    на `system_prompt` следующих вызовов LLM, но не переписывает уже
    сохранённые сообщения — на реальной SQLite (`build_profile_repository`,
    не fake).
    """

    async def test_switching_profile_changes_system_prompt_without_rewriting_history(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        other_profile_id = uuid4()
        async with session_factory() as session:
            session.add(
                ProfileORM(
                    id=other_profile_id,
                    name="Креативный",
                    description="Образный, нестандартный стиль.",
                    system_instruction="Отвечай образно, с метафорами.",
                    response_style="образный",
                    target_audience="тесты",
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

        provider = FakeLLMProvider()
        use_case = _make_use_case(session_factory, provider)

        first_result = await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=1001,
                message_text="Первое сообщение",
                correlation_id=CorrelationId("corr-1"),
            )
        )

        async with session_factory() as session:
            rows_before_switch = (
                (
                    await session.execute(
                        select(MessageORM)
                        .where(MessageORM.conversation_id == first_result.conversation_id)
                        .order_by(MessageORM.created_at, MessageORM.id)
                    )
                )
                .scalars()
                .all()
            )
        contents_before_switch = [row.content for row in rows_before_switch]

        # Переключаем профиль пользователя — через тот же ProfileRepository,
        # что и SelectProfile use case (S3-06), напрямую на реальной SQLite.
        conversation_repositories_factory = build_conversation_repositories_factory(session_factory)
        async with conversation_repositories_factory() as repositories:
            stored_user = await repositories.users.get_by_telegram_user_id(1001)
            assert stored_user is not None
            selected = await repositories.profiles.select_profile(stored_user.id, other_profile_id)
            assert selected is not None
            assert selected.id == other_profile_id

        second_result = await use_case.execute(
            ProcessUserMessageCommand(
                telegram_user_id=1001,
                message_text="Второе сообщение",
                correlation_id=CorrelationId("corr-2"),
            )
        )

        assert second_result.conversation_id == first_result.conversation_id
        assert len(provider.received_requests) == 2
        # Sprint 4 (ADR-4.7): system_prompt — склейка секций Prompt Engine, проверяем вхождение, не равенство.
        assert "Отвечай образно, с метафорами." in provider.received_requests[1].system_prompt
        assert provider.received_requests[1].system_prompt != provider.received_requests[0].system_prompt

        async with session_factory() as session:
            rows_after_switch = (
                (
                    await session.execute(
                        select(MessageORM)
                        .where(MessageORM.conversation_id == first_result.conversation_id)
                        .order_by(MessageORM.created_at, MessageORM.id)
                    )
                )
                .scalars()
                .all()
            )

        # Переключение профиля не изменило содержимое уже сохранённых сообщений.
        assert [row.content for row in rows_after_switch[: len(contents_before_switch)]] == contents_before_switch
