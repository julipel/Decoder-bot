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
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.application.conversation.dto import LLMRequest, LLMResponse, ProcessUserMessageCommand
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
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


def _make_use_case(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    provider: FakeLLMProvider,
) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=build_conversation_repositories_factory(session_factory),
        default_model=ModelId("openai/gpt-4o-mini"),
        system_prompt="Ты — ассистент.",
        temperature=0.7,
        max_tokens=512,
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
