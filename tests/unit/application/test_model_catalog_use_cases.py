"""
Тесты use case'ов каталога моделей (application/model_catalog/use_cases/*,
Sprint 7, задача S7-05, ADR-7.7/ADR-7.9).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` (`model_selection`/`users`) и
`tests/support/fake_model_catalog.py::FakeModelCatalogRepository` — без
SQLAlchemy, по стилю `test_memory_use_cases.py`.
"""

from __future__ import annotations

import json

import pytest
from tests.support.fake_conversation_repositories import (
    FakeModelSelectionRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)
from tests.support.fake_model_catalog import FakeModelCatalogRepository, make_ai_model

from dekoder.application.model_catalog.dto import (
    GetSelectedModelCommand,
    ListAvailableModelsCommand,
    SelectModelCommand,
)
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.errors import ApplicationError
from dekoder.shared.logging import configure_logging


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


class TestListAvailableModels:
    async def test_marks_previously_selected_model_as_active(self) -> None:
        available = make_ai_model("openai/gpt-4o-mini")
        other = make_ai_model("anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet")
        catalog = FakeModelCatalogRepository([available, other])

        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(111)
        selections = FakeModelSelectionRepository({user.id: ModelId("anthropic/claude-3.5-sonnet")})
        factory = make_in_memory_repositories_factory(users=users, model_selection=selections)

        use_case = ListAvailableModels(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            ListAvailableModelsCommand(telegram_user_id=111, correlation_id=CorrelationId("corr-1"))
        )

        assert {model.model_id for model in result.models} == {available.model_id, other.model_id}
        assert result.active_model_id == ModelId("anthropic/claude-3.5-sonnet")

    async def test_unknown_user_has_no_active_model_but_sees_full_list(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        factory = make_in_memory_repositories_factory()

        use_case = ListAvailableModels(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            ListAvailableModelsCommand(telegram_user_id=999, correlation_id=CorrelationId("corr-1"))
        )

        assert len(result.models) == 1
        assert result.active_model_id is None


class TestGetSelectedModel:
    async def test_returns_none_when_user_unknown(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        factory = make_in_memory_repositories_factory()

        use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            GetSelectedModelCommand(telegram_user_id=123, correlation_id=CorrelationId("corr-1"))
        )

        assert result.model is None

    async def test_returns_none_when_no_selection_made(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(222)
        factory = make_in_memory_repositories_factory(users=users)

        use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            GetSelectedModelCommand(telegram_user_id=222, correlation_id=CorrelationId("corr-1"))
        )

        assert result.model is None

    async def test_returns_resolved_model_when_selection_exists(self) -> None:
        model = make_ai_model("openai/gpt-4o-mini")
        catalog = FakeModelCatalogRepository([model])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(333)
        selections = FakeModelSelectionRepository({user.id: model.model_id})
        factory = make_in_memory_repositories_factory(users=users, model_selection=selections)

        use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            GetSelectedModelCommand(telegram_user_id=333, correlation_id=CorrelationId("corr-1"))
        )

        assert result.model == model

    async def test_stale_selection_pointing_at_removed_model_returns_none(self) -> None:
        """AC-3 (S7-05): устойчивость к изменению каталога после того, как выбор был сделан."""
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(444)
        selections = FakeModelSelectionRepository({user.id: ModelId("removed/model")})
        factory = make_in_memory_repositories_factory(users=users, model_selection=selections)

        use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            GetSelectedModelCommand(telegram_user_id=444, correlation_id=CorrelationId("corr-1"))
        )

        assert result.model is None


class TestSelectModel:
    async def test_selects_available_model_successfully(self) -> None:
        model = make_ai_model("openai/gpt-4o-mini", availability=ModelAvailability.AVAILABLE)
        catalog = FakeModelCatalogRepository([model])
        factory = make_in_memory_repositories_factory()

        use_case = SelectModel(repositories=factory, model_catalog=catalog)
        result = await use_case.execute(
            SelectModelCommand(telegram_user_id=555, model_id=model.model_id, correlation_id=CorrelationId("corr-1"))
        )

        assert result.model == model

        get_use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        selected = await get_use_case.execute(
            GetSelectedModelCommand(telegram_user_id=555, correlation_id=CorrelationId("corr-1"))
        )
        assert selected.model == model

    async def test_rejects_unavailable_model_without_calling_select(self) -> None:
        """AC-1 (S7-05): недоступная модель — ошибка, ModelSelectionRepository.select не вызывается."""
        unavailable = make_ai_model("anthropic/claude-3-haiku", availability=ModelAvailability.UNAVAILABLE)
        catalog = FakeModelCatalogRepository([unavailable])
        users = FakeUserRepository()
        factory = make_in_memory_repositories_factory(users=users)

        use_case = SelectModel(repositories=factory, model_catalog=catalog)

        with pytest.raises(ApplicationError) as excinfo:
            await use_case.execute(
                SelectModelCommand(
                    telegram_user_id=666, model_id=unavailable.model_id, correlation_id=CorrelationId("corr-1")
                )
            )

        assert excinfo.value.code == "MODEL_UNAVAILABLE"
        # Ошибка поднимается до входа в транзакцию — пользователь не
        # создан, `select()` не вызывался (иначе бы был вызван get_or_create).
        assert await users.get_by_telegram_user_id(666) is None

    async def test_rejects_unknown_model_without_calling_select(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        users = FakeUserRepository()
        factory = make_in_memory_repositories_factory(users=users)

        use_case = SelectModel(repositories=factory, model_catalog=catalog)

        with pytest.raises(ApplicationError) as excinfo:
            await use_case.execute(
                SelectModelCommand(
                    telegram_user_id=777,
                    model_id=ModelId("does-not-exist/model"),
                    correlation_id=CorrelationId("corr-1"),
                )
            )

        assert excinfo.value.code == "MODEL_NOT_FOUND"
        assert await users.get_by_telegram_user_id(777) is None

    async def test_creates_user_automatically_when_unknown(self) -> None:
        model = make_ai_model("openai/gpt-4o-mini")
        catalog = FakeModelCatalogRepository([model])
        users = FakeUserRepository()
        factory = make_in_memory_repositories_factory(users=users)

        use_case = SelectModel(repositories=factory, model_catalog=catalog)
        await use_case.execute(
            SelectModelCommand(telegram_user_id=888, model_id=model.model_id, correlation_id=CorrelationId("corr-1"))
        )

        created_user = await users.get_by_telegram_user_id(888)
        assert created_user is not None

    async def test_repeated_selection_replaces_previous_choice(self) -> None:
        first_model = make_ai_model("openai/gpt-4o-mini")
        second_model = make_ai_model("anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet")
        catalog = FakeModelCatalogRepository([first_model, second_model])
        factory = make_in_memory_repositories_factory()

        use_case = SelectModel(repositories=factory, model_catalog=catalog)
        await use_case.execute(
            SelectModelCommand(
                telegram_user_id=999, model_id=first_model.model_id, correlation_id=CorrelationId("corr-1")
            )
        )
        await use_case.execute(
            SelectModelCommand(
                telegram_user_id=999, model_id=second_model.model_id, correlation_id=CorrelationId("corr-1")
            )
        )

        get_use_case = GetSelectedModel(repositories=factory, model_catalog=catalog)
        selected = await get_use_case.execute(
            GetSelectedModelCommand(telegram_user_id=999, correlation_id=CorrelationId("corr-1"))
        )
        assert selected.model == second_model


class TestSelectModelAuditLog:
    """Sprint 9, S9-04 (ADR-9.4): model_selected переведён на log_audit_event()."""

    async def test_logs_selection_event_marked_as_audit(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        model = make_ai_model("openai/gpt-4o-mini", availability=ModelAvailability.AVAILABLE)
        catalog = FakeModelCatalogRepository([model])
        factory = make_in_memory_repositories_factory()
        use_case = SelectModel(repositories=factory, model_catalog=catalog)

        result = await use_case.execute(
            SelectModelCommand(telegram_user_id=1010, model_id=model.model_id, correlation_id=CorrelationId("corr-1"))
        )

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "model_selected"
        assert entry["model_id"] == result.model.model_id.value
        assert entry["audit"] is True
