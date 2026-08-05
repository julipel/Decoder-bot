"""Тесты доменной сущности `PromptTemplate` (domain/prompt/entities.py, задача S4-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from dekoder.domain.prompt.entities import PromptTemplate, PromptTemplateStatus


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_template(**overrides: object) -> PromptTemplate:
    defaults: dict[str, object] = {
        "id": "base_instruction",
        "name": "Базовая инструкция",
        "version": "1.0.0",
        "purpose": "base_instruction",
        "text": "Ты — персональный ассистент «Декодер».",
        "required_variables": (),
        "status": PromptTemplateStatus.ACTIVE,
        "updated_at": _now(),
    }
    defaults.update(overrides)
    return PromptTemplate(**defaults)  # type: ignore[arg-type]


class TestPromptTemplateCreation:
    def test_creates_valid_template(self) -> None:
        template = _make_template()

        assert template.id == "base_instruction"
        assert template.status is PromptTemplateStatus.ACTIVE

    def test_accepts_required_variables(self) -> None:
        template = _make_template(required_variables=("system_instruction", "response_style"))

        assert template.required_variables == ("system_instruction", "response_style")

    def test_is_frozen(self) -> None:
        template = _make_template()

        with pytest.raises(dataclasses.FrozenInstanceError):
            template.text = "другое"  # type: ignore[misc]


class TestPromptTemplateInvariants:
    def test_empty_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="id"):
            _make_template(id="")

    def test_blank_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            _make_template(name="   ")

    def test_empty_version_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="version"):
            _make_template(version="")

    def test_empty_purpose_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="purpose"):
            _make_template(purpose="")

    def test_blank_text_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="text"):
            _make_template(text="   ")

    def test_naive_updated_at_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _make_template(updated_at=datetime(2026, 1, 1, 12, 0, 0))


class TestPromptTemplateStatus:
    def test_has_active_and_archived_values(self) -> None:
        assert PromptTemplateStatus.ACTIVE.value == "active"
        assert PromptTemplateStatus.ARCHIVED.value == "archived"
