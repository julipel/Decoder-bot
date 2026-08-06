"""Тесты доменной сущности `ModelSelection` (domain/model_catalog/entities.py, задача S7-04, ADR-7.5)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import ModelSelection


def _make_selection(**overrides: object) -> ModelSelection:
    defaults: dict[str, object] = {
        "user_id": uuid4(),
        "model_id": ModelId("openai/gpt-4o-mini"),
        "selected_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ModelSelection(**defaults)  # type: ignore[arg-type]


class TestModelSelectionCreation:
    def test_creates_valid_selection(self) -> None:
        user_id = uuid4()
        model_id = ModelId("anthropic/claude-3.5-sonnet")

        selection = _make_selection(user_id=user_id, model_id=model_id)

        assert selection.user_id == user_id
        assert selection.model_id == model_id

    def test_model_id_is_live_value_object(self) -> None:
        selection = _make_selection()

        assert selection.model_id == ModelId("openai/gpt-4o-mini")


class TestModelSelectionImmutability:
    def test_is_frozen(self) -> None:
        selection = _make_selection()

        with pytest.raises(dataclasses.FrozenInstanceError):
            selection.model_id = ModelId("other/model")  # type: ignore[misc]
