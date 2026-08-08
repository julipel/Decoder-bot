"""
Интеграционные тесты ClearConversation (Sprint 2, задача S2-09) —
реальные SQLAlchemy-репозитории поверх временной SQLite (`tmp_path`, схема
через `Base.metadata.create_all()`, единственное допустимое исключение для
тестового окружения, backlog_2.md §3), тот же стиль, что и
`tests/integration/test_start_new_conversation_persistence.py` (задача S2-07).

Проверяет ровно то, что требует backlog_2_tasks.md (S2-09):
- после очистки история пуста (`MessageRepository.history()` → `[]`);
- `Conversation` продолжает существовать (`ConversationRepository.get_by_id()`
  не `None`) и остаётся активным (`closed_at is None`);
- следующее сообщение, сохранённое после очистки, попадает в ТОТ ЖЕ
  `conversation_id`, что и до неё;
- сообщения ДРУГОГО диалога (другого пользователя и другого — закрытого —
  диалога того же пользователя) не удаляются при очистке текущего
  активного диалога.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.application.conversation.dto import ClearConversationCommand, ClearConversationStatus
from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.domain.identifiers import CorrelationId


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'clear-conversation.db'}"
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


def _make_message(conversation_id: UUID, role: MessageRole, content: str, created_at: datetime) -> Message:
    return Message(id=uuid4(), conversation_id=conversation_id, role=role, content=content, created_at=created_at)


class TestClearsActiveConversationHistory:
    """Обязательный сценарий: очистка удаляет всю историю активного диалога, сам диалог остаётся."""

    async def test_history_is_empty_and_conversation_still_exists_and_active(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(5050)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            first_created_at = datetime.now(UTC)
            await repositories.messages.save(
                _make_message(conversation.id, MessageRole.USER, "Привет!", first_created_at)
            )
            await repositories.messages.save(
                _make_message(
                    conversation.id, MessageRole.ASSISTANT, "Здравствуйте!", first_created_at + timedelta(seconds=1)
                )
            )

        use_case = ClearConversation(repositories=repositories_factory)
        result = await use_case.execute(
            ClearConversationCommand(telegram_user_id=5050, correlation_id=CorrelationId("corr-1"))
        )

        assert result.status == ClearConversationStatus.CLEARED
        assert result.conversation_id == conversation.id
        assert result.deleted_count == 2

        async with repositories_factory() as repositories:
            history = await repositories.messages.history(conversation.id)
            stored_conversation = await repositories.conversations.get_by_id(conversation.id)

        assert history == []
        assert stored_conversation is not None
        assert stored_conversation.closed_at is None
        assert stored_conversation.is_active

    async def test_next_message_is_saved_into_same_conversation_id(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(5151)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            await repositories.messages.save(
                _make_message(conversation.id, MessageRole.USER, "Первое сообщение", datetime.now(UTC))
            )

        use_case = ClearConversation(repositories=repositories_factory)
        await use_case.execute(ClearConversationCommand(telegram_user_id=5151, correlation_id=CorrelationId("corr-1")))

        async with repositories_factory() as repositories:
            active_after_clear = await repositories.conversations.get_active_by_user_id(user.id)
            assert active_after_clear is not None
            assert active_after_clear.id == conversation.id
            await repositories.messages.save(
                _make_message(conversation.id, MessageRole.USER, "Сообщение после очистки", datetime.now(UTC))
            )

        async with repositories_factory() as repositories:
            history = await repositories.messages.history(conversation.id)

        assert [message.content for message in history] == ["Сообщение после очистки"]
        assert all(message.conversation_id == conversation.id for message in history)


class TestDoesNotAffectOtherConversations:
    """
    Обязательный сценарий: очистка текущего активного диалога не трогает
    сообщения других диалогов — ни другого пользователя, ни закрытого
    диалога того же пользователя.
    """

    async def test_other_users_conversation_is_untouched(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user_a = await repositories.users.get_or_create_by_telegram_user_id(6060)
            conversation_a = await repositories.conversations.get_or_create_active(user_a.id)
            await repositories.messages.save(
                _make_message(conversation_a.id, MessageRole.USER, "От пользователя A", datetime.now(UTC))
            )

            user_b = await repositories.users.get_or_create_by_telegram_user_id(6061)
            conversation_b = await repositories.conversations.get_or_create_active(user_b.id)
            await repositories.messages.save(
                _make_message(conversation_b.id, MessageRole.USER, "От пользователя B", datetime.now(UTC))
            )

        use_case = ClearConversation(repositories=repositories_factory)
        result = await use_case.execute(
            ClearConversationCommand(telegram_user_id=6060, correlation_id=CorrelationId("corr-1"))
        )

        assert result.status == ClearConversationStatus.CLEARED
        assert result.conversation_id == conversation_a.id

        async with repositories_factory() as repositories:
            history_a = await repositories.messages.history(conversation_a.id)
            history_b = await repositories.messages.history(conversation_b.id)

        assert history_a == []
        assert [message.content for message in history_b] == ["От пользователя B"]

    async def test_same_users_closed_conversation_is_untouched(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(6070)
            old_conversation = await repositories.conversations.get_or_create_active(user.id)
            await repositories.messages.save(
                _make_message(old_conversation.id, MessageRole.USER, "Старая история", datetime.now(UTC))
            )
            old_conversation.close(datetime.now(UTC))
            await repositories.conversations.close(old_conversation)

            new_conversation = await repositories.conversations.get_or_create_active(user.id)
            await repositories.messages.save(
                _make_message(new_conversation.id, MessageRole.USER, "Новая история", datetime.now(UTC))
            )

        use_case = ClearConversation(repositories=repositories_factory)
        result = await use_case.execute(
            ClearConversationCommand(telegram_user_id=6070, correlation_id=CorrelationId("corr-1"))
        )

        assert result.status == ClearConversationStatus.CLEARED
        assert result.conversation_id == new_conversation.id

        async with repositories_factory() as repositories:
            old_history = await repositories.messages.history(old_conversation.id)
            new_history = await repositories.messages.history(new_conversation.id)
            stored_old_conversation = await repositories.conversations.get_by_id(old_conversation.id)

        assert [message.content for message in old_history] == ["Старая история"]
        assert new_history == []
        assert stored_old_conversation is not None
        assert not stored_old_conversation.is_active


class TestMissingUserOrConversation:
    """Обязательный сценарий: пользователь или активный диалог отсутствует — ничего не создаётся и не изменяется."""

    async def test_missing_user_changes_nothing(
        self,
        repositories_factory: ConversationRepositoriesFactory,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        use_case = ClearConversation(repositories=repositories_factory)

        result = await use_case.execute(
            ClearConversationCommand(telegram_user_id=999999, correlation_id=CorrelationId("corr-1"))
        )

        assert result.status == ClearConversationStatus.NO_ACTIVE_CONVERSATION
        assert result.conversation_id is None
        assert result.deleted_count == 0

        async with session_factory() as session:
            rows = (await session.execute(select(ConversationORM))).scalars().all()
        assert rows == []

    async def test_user_without_active_conversation_changes_nothing(
        self,
        repositories_factory: ConversationRepositoriesFactory,
    ) -> None:
        async with repositories_factory() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(7070)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            conversation.close(datetime.now(UTC))
            await repositories.conversations.close(conversation)

        use_case = ClearConversation(repositories=repositories_factory)
        result = await use_case.execute(
            ClearConversationCommand(telegram_user_id=7070, correlation_id=CorrelationId("corr-1"))
        )

        assert result.status == ClearConversationStatus.NO_ACTIVE_CONVERSATION
        assert result.conversation_id is None
        assert result.deleted_count == 0

        async with repositories_factory() as repositories:
            stored = await repositories.conversations.get_by_id(conversation.id)
        assert stored is not None
        assert not stored.is_active
