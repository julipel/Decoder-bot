"""
Тесты `bootstrap/repositories.py` (задачи S2-03/S2-04/S2-05/S2-06) —
единственной точки сборки `UserRepository`/`ConversationRepository`/
`MessageRepository` поверх переданной `AsyncSession`, а также (S2-06)
`ConversationRepositoriesFactory` поверх единой фабрики сессий. Проверяет,
что фабрики возвращают структурно совместимые реализации, которые реально
работают поверх SQLite (не мок).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.application.conversation.ports import ConversationRepository, MessageRepository
from dekoder.application.user.ports import UserRepository
from dekoder.bootstrap.repositories import (
    build_conversation_repositories_factory,
    build_conversation_repository,
    build_message_repository,
    build_user_repository,
)
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'repositories-bootstrap.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


class TestBuildUserRepository:
    async def test_returns_a_working_repository_satisfying_the_port(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = build_user_repository(session)

            assert isinstance(repository, UserRepository)

            created = await repository.get_or_create_by_telegram_user_id(4242)
            fetched = await repository.get_by_id(created.id)

        assert fetched == created


class TestBuildConversationRepository:
    async def test_returns_a_working_repository_satisfying_the_port(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_repository = build_user_repository(session)
            user = await user_repository.get_or_create_by_telegram_user_id(4343)

            repository = build_conversation_repository(session)

            assert isinstance(repository, ConversationRepository)

            created = await repository.get_or_create_active(user.id)
            fetched = await repository.get_by_id(created.id)

        assert fetched == created


class TestBuildMessageRepository:
    async def test_returns_a_working_repository_satisfying_the_port(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_repository = build_user_repository(session)
            user = await user_repository.get_or_create_by_telegram_user_id(4444)

            conversation_repository = build_conversation_repository(session)
            conversation = await conversation_repository.get_or_create_active(user.id)

            repository = build_message_repository(session)

            assert isinstance(repository, MessageRepository)

            message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="hello",
                created_at=datetime.now(UTC),
            )
            saved = await repository.save(message)
            history = await repository.history(conversation.id)

        assert history == [saved]


class TestBuildConversationRepositoriesFactory:
    """
    Задача S2-06: каждый вызов фабрики — новая короткая транзакция
    (`session_scope()` поверх новой `AsyncSession`), commit при успешном
    выходе из `async with`, rollback при исключении.
    """

    async def test_each_call_opens_an_independent_committed_transaction(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        repositories_factory = build_conversation_repositories_factory(session_factory)

        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(5151)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="hello",
                created_at=datetime.now(UTC),
            )
            await repositories.messages.save(message)

        # Новый вызов -> новая транзакция/сессия, но данные из предыдущей
        # уже закоммичены и видны.
        async with repositories_factory() as repositories:
            history = await repositories.messages.history(conversation.id)

        assert [m.content for m in history] == ["hello"]

    async def test_exception_inside_the_scope_rolls_back_uncommitted_writes(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        repositories_factory = build_conversation_repositories_factory(session_factory)

        user = None
        with pytest.raises(RuntimeError):
            async with repositories_factory() as repositories:
                user = await repositories.users.get_or_create_by_telegram_user_id(6161)
                conversation = await repositories.conversations.get_or_create_active(user.id)
                message = Message(
                    id=uuid4(),
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content="not committed",
                    created_at=datetime.now(UTC),
                )
                await repositories.messages.save(message)
                raise RuntimeError("boom")

        assert user is not None
        async with repositories_factory() as repositories:
            active_conversation = await repositories.conversations.get_active_by_user_id(user.id)

        # get_or_create_by_telegram_user_id/get_or_create_active коммитят
        # сами себя (S2-03/S2-04) — пользователь и диалог остаются, но
        # save() сообщения (flush без commit) откатился вместе со всей
        # транзакцией из-за необработанного исключения внутри блока.
        assert active_conversation is not None
        async with repositories_factory() as repositories:
            history = await repositories.messages.history(active_conversation.id)
        assert history == []
