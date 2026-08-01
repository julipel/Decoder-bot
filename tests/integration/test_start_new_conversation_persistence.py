"""
Интеграционные тесты StartNewConversation (Sprint 2, задача S2-07) —
реальные SQLAlchemy-репозитории поверх временной SQLite (`tmp_path`, схема
через `Base.metadata.create_all()`, единственное допустимое исключение для
тестового окружения, backlog_2.md §3), тот же стиль, что и
`tests/integration/test_process_user_message_persistence.py` (задача S2-06).

Проверяет ровно то, что требует backlog_2_tasks.md (S2-07):
- полный цикл создания нового диалога через реальные репозитории и БД;
- одновременно существует только один активный диалог пользователя после
  StartNewConversation (старый closed, новый active, `uq_conversations_active_user`
  не нарушен — второй активный не был бы принят БД, если бы старый не был
  закрыт первым);
- история старого (закрытого) диалога остаётся читаемой через
  `MessageRepository.history()` после закрытия.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.application.conversation.dto import StartNewConversationCommand
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'start-new-conversation.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


@pytest.fixture
def repositories_factory(session_factory: async_sessionmaker) -> ConversationRepositoriesFactory:  # type: ignore[type-arg]
    return build_conversation_repositories_factory(session_factory)


class TestFullCycle:
    """Обязательный сценарий: полный цикл создания нового диалога через реальные репозитории и реальную БД."""

    async def test_start_new_conversation_creates_active_conversation_in_database(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(4242)
            first_conversation = await repositories.conversations.get_or_create_active(user.id)

        use_case = StartNewConversation(repositories=repositories_factory)
        result = await use_case.execute(StartNewConversationCommand(telegram_user_id=4242))

        assert result.conversation_id is not None
        assert result.conversation_id != first_conversation.id

        async with session_factory() as session:
            row = await session.get(ConversationORM, result.conversation_id)
        assert row is not None
        assert row.closed_at is None
        assert row.user_id == user.id

    async def test_missing_user_creates_nothing_in_database(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        use_case = StartNewConversation(repositories=repositories_factory)

        result = await use_case.execute(StartNewConversationCommand(telegram_user_id=999999))

        assert result.conversation_id is None
        async with session_factory() as session:
            rows = (await session.execute(select(ConversationORM))).scalars().all()
        assert rows == []


class TestSingleActiveConversationInvariant:
    """
    Обязательный сценарий: после StartNewConversation одновременно существует
    только один активный диалог пользователя (старый closed, новый active) —
    БД-инвариант `uq_conversations_active_user` не нарушен.
    """

    async def test_only_one_active_conversation_remains_after_start_new(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(1010)
            old_conversation = await repositories.conversations.get_or_create_active(user.id)

        use_case = StartNewConversation(repositories=repositories_factory)
        result = await use_case.execute(StartNewConversationCommand(telegram_user_id=1010))

        async with session_factory() as session:
            rows = (
                (await session.execute(select(ConversationORM).where(ConversationORM.user_id == user.id)))
                .scalars()
                .all()
            )

        assert len(rows) == 2
        active_rows = [row for row in rows if row.closed_at is None]
        closed_rows = [row for row in rows if row.closed_at is not None]
        assert len(active_rows) == 1
        assert len(closed_rows) == 1
        assert active_rows[0].id == result.conversation_id
        assert closed_rows[0].id == old_conversation.id

    async def test_repeated_calls_keep_exactly_one_active_conversation(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(1111)

        use_case = StartNewConversation(repositories=repositories_factory)
        await use_case.execute(StartNewConversationCommand(telegram_user_id=1111))
        await use_case.execute(StartNewConversationCommand(telegram_user_id=1111))
        third_result = await use_case.execute(StartNewConversationCommand(telegram_user_id=1111))

        async with session_factory() as session:
            rows = (
                (await session.execute(select(ConversationORM).where(ConversationORM.user_id == user.id)))
                .scalars()
                .all()
            )

        assert len(rows) == 3
        active_rows = [row for row in rows if row.closed_at is None]
        assert len(active_rows) == 1
        assert active_rows[0].id == third_result.conversation_id


class TestOldConversationHistoryPreserved:
    """
    Обязательный сценарий: история старого (закрытого) диалога сохраняется —
    сообщения остаются читаемыми через `MessageRepository.history()` после
    закрытия диалога StartNewConversation.
    """

    async def test_old_conversation_messages_remain_readable_after_closing(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(2020)
            old_conversation = await repositories.conversations.get_or_create_active(user.id)
            first_created_at = datetime.now(UTC)
            second_created_at = first_created_at + timedelta(seconds=1)
            await repositories.messages.save(
                Message(
                    id=uuid4(),
                    conversation_id=old_conversation.id,
                    role=MessageRole.USER,
                    content="Привет!",
                    created_at=first_created_at,
                )
            )
            await repositories.messages.save(
                Message(
                    id=uuid4(),
                    conversation_id=old_conversation.id,
                    role=MessageRole.ASSISTANT,
                    content="Здравствуйте!",
                    created_at=second_created_at,
                )
            )

        use_case = StartNewConversation(repositories=repositories_factory)
        await use_case.execute(StartNewConversationCommand(telegram_user_id=2020))

        async with repositories_factory() as repositories:
            history = await repositories.messages.history(old_conversation.id)
            stored_old_conversation = await repositories.conversations.get_by_id(old_conversation.id)

        assert [message.content for message in history] == ["Привет!", "Здравствуйте!"]
        assert [message.role for message in history] == [MessageRole.USER, MessageRole.ASSISTANT]
        assert stored_old_conversation is not None
        assert not stored_old_conversation.is_active
