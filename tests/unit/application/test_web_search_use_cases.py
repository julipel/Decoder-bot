"""
Тесты use case'ов персонального переключателя веб-поиска
(application/conversation/use_cases/{get_web_search_status,
set_web_search_enabled}.py, внеспринтовая задача, 2026-09-09).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` (`web_search`/`users`) — без
SQLAlchemy, по стилю `test_model_catalog_use_cases.py`.
"""

from __future__ import annotations

from tests.support.fake_conversation_repositories import (
    FakeUserRepository,
    FakeWebSearchSettingRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import GetWebSearchStatusCommand, SetWebSearchEnabledCommand
from dekoder.application.conversation.use_cases.get_web_search_status import GetWebSearchStatus
from dekoder.application.conversation.use_cases.set_web_search_enabled import SetWebSearchEnabled
from dekoder.shared.domain.identifiers import CorrelationId


class TestGetWebSearchStatus:
    async def test_returns_false_when_user_unknown(self) -> None:
        factory = make_in_memory_repositories_factory()

        use_case = GetWebSearchStatus(repositories=factory)
        result = await use_case.execute(
            GetWebSearchStatusCommand(telegram_user_id=123, correlation_id=CorrelationId("corr-1"))
        )

        assert result.enabled is False

    async def test_returns_false_when_never_toggled(self) -> None:
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(111)
        factory = make_in_memory_repositories_factory(users=users)

        use_case = GetWebSearchStatus(repositories=factory)
        result = await use_case.execute(
            GetWebSearchStatusCommand(telegram_user_id=111, correlation_id=CorrelationId("corr-1"))
        )

        assert result.enabled is False

    async def test_returns_true_after_enabled(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(222)
        web_search = FakeWebSearchSettingRepository({user.id: True})
        factory = make_in_memory_repositories_factory(users=users, web_search=web_search)

        use_case = GetWebSearchStatus(repositories=factory)
        result = await use_case.execute(
            GetWebSearchStatusCommand(telegram_user_id=222, correlation_id=CorrelationId("corr-1"))
        )

        assert result.enabled is True


class TestSetWebSearchEnabled:
    async def test_enables_for_new_user(self) -> None:
        factory = make_in_memory_repositories_factory()

        use_case = SetWebSearchEnabled(repositories=factory)
        result = await use_case.execute(
            SetWebSearchEnabledCommand(telegram_user_id=333, enabled=True, correlation_id=CorrelationId("corr-1"))
        )

        assert result.enabled is True

        status = await GetWebSearchStatus(repositories=factory).execute(
            GetWebSearchStatusCommand(telegram_user_id=333, correlation_id=CorrelationId("corr-2"))
        )
        assert status.enabled is True

    async def test_toggle_replaces_previous_value(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(444)
        web_search = FakeWebSearchSettingRepository({user.id: True})
        factory = make_in_memory_repositories_factory(users=users, web_search=web_search)

        use_case = SetWebSearchEnabled(repositories=factory)
        result = await use_case.execute(
            SetWebSearchEnabledCommand(telegram_user_id=444, enabled=False, correlation_id=CorrelationId("corr-1"))
        )

        assert result.enabled is False

    async def test_two_users_keep_independent_settings(self) -> None:
        factory = make_in_memory_repositories_factory()
        use_case = SetWebSearchEnabled(repositories=factory)

        await use_case.execute(
            SetWebSearchEnabledCommand(telegram_user_id=555, enabled=True, correlation_id=CorrelationId("corr-1"))
        )
        await use_case.execute(
            SetWebSearchEnabledCommand(telegram_user_id=666, enabled=False, correlation_id=CorrelationId("corr-2"))
        )

        get_use_case = GetWebSearchStatus(repositories=factory)
        status_a = await get_use_case.execute(
            GetWebSearchStatusCommand(telegram_user_id=555, correlation_id=CorrelationId("corr-3"))
        )
        status_b = await get_use_case.execute(
            GetWebSearchStatusCommand(telegram_user_id=666, correlation_id=CorrelationId("corr-4"))
        )

        assert status_a.enabled is True
        assert status_b.enabled is False
