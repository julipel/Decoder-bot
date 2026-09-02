"""
Интеграционные тесты `FileTemplateRepository` (Sprint 4, задача S4-04,
ADR-4.2) — часть их — round-trip на временном каталоге шаблонов
(`tmp_path`, по стилю `test_profile_repository.py`), часть — на реальном
сид-каталоге `infrastructure/prompts/templates/` (проверка содержимого,
требуемого ADR-4.7/S4-04 AC-2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dekoder.domain.prompt.entities import PromptTemplateStatus
from dekoder.infrastructure.prompts.file_template_repository import (
    DEFAULT_TEMPLATES_DIR,
    FileTemplateRepository,
)
from dekoder.shared.errors import InfrastructureError

# Текст сознательно меняется по продуктовым причинам (внеспринтовый
# фикс 2026-09-02 — заказчик жаловался на «роботизированность» ответов,
# base_instruction переписан на более человечный тон, версия шаблона
# бумпнута 1.0.0 → 1.1.0 в manifest.json) — при следующем таком
# изменении обновляйте эту константу вместе с файлом, не наоборот.
_EXPECTED_BASE_INSTRUCTION_TEXT = (
    "Ты — персональный ассистент «Декодер». Общайся с пользователем как живой человек в переписке — "
    "естественным разговорным языком, без канцелярита и без ощущения, что отвечает бот. Отвечай по "
    "существу вопроса, не растягивая ответ там, где хватит короткой фразы."
)


def _write_manifest(directory: Path, entries: list[dict[str, object]]) -> None:
    (directory / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")


class TestFileTemplateRepositoryRoundTrip:
    def test_loads_template_matching_file_contents(self, tmp_path: Path) -> None:
        (tmp_path / "greeting.txt").write_text("Привет, $name!", encoding="utf-8")
        _write_manifest(
            tmp_path,
            [
                {
                    "id": "greeting",
                    "name": "Приветствие",
                    "version": "1.0.0",
                    "purpose": "greeting",
                    "text_file": "greeting.txt",
                    "required_variables": ["name"],
                    "status": "active",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )

        repository = FileTemplateRepository(templates_dir=tmp_path)
        template = repository.get("greeting")

        assert template.text == "Привет, $name!"
        assert template.required_variables == ("name",)
        assert template.status is PromptTemplateStatus.ACTIVE

    def test_list_all_returns_every_loaded_template(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("A", encoding="utf-8")
        (tmp_path / "b.txt").write_text("B", encoding="utf-8")
        _write_manifest(
            tmp_path,
            [
                {
                    "id": "a",
                    "name": "A",
                    "version": "1.0.0",
                    "purpose": "a",
                    "text_file": "a.txt",
                    "required_variables": [],
                    "status": "active",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "id": "b",
                    "name": "B",
                    "version": "1.0.0",
                    "purpose": "b",
                    "text_file": "b.txt",
                    "required_variables": [],
                    "status": "active",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            ],
        )

        repository = FileTemplateRepository(templates_dir=tmp_path)

        assert {template.id for template in repository.list_all()} == {"a", "b"}

    def test_get_unknown_template_raises_infrastructure_error(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, [])

        repository = FileTemplateRepository(templates_dir=tmp_path)

        with pytest.raises(InfrastructureError, match="не найден"):
            repository.get("does-not-exist")

    def test_missing_manifest_raises_infrastructure_error(self, tmp_path: Path) -> None:
        with pytest.raises(InfrastructureError, match="манифест"):
            FileTemplateRepository(templates_dir=tmp_path)

    def test_missing_text_file_raises_infrastructure_error(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            [
                {
                    "id": "missing",
                    "name": "Missing",
                    "version": "1.0.0",
                    "purpose": "missing",
                    "text_file": "does_not_exist.txt",
                    "required_variables": [],
                    "status": "active",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )

        with pytest.raises(InfrastructureError, match="файл шаблона"):
            FileTemplateRepository(templates_dir=tmp_path)

    def test_loading_is_deterministic(self, tmp_path: Path) -> None:
        (tmp_path / "x.txt").write_text("X content", encoding="utf-8")
        _write_manifest(
            tmp_path,
            [
                {
                    "id": "x",
                    "name": "X",
                    "version": "1.0.0",
                    "purpose": "x",
                    "text_file": "x.txt",
                    "required_variables": [],
                    "status": "active",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )

        first = FileTemplateRepository(templates_dir=tmp_path).list_all()
        second = FileTemplateRepository(templates_dir=tmp_path).list_all()

        assert first == second


class TestSeedTemplates:
    """Проверяет реальный сид-каталог `infrastructure/prompts/templates/`."""

    def test_default_templates_dir_is_used_without_explicit_argument(self) -> None:
        repository = FileTemplateRepository()

        assert {template.id for template in repository.list_all()} == {
            "base_instruction",
            "safety_rules",
            "profile_parameters",
            "memory_placeholder",
            "knowledge_placeholder",
            "response_format",
        }

    def test_base_instruction_matches_expected_content(self) -> None:
        repository = FileTemplateRepository()

        template = repository.get("base_instruction")

        assert template.text == _EXPECTED_BASE_INSTRUCTION_TEXT

    def test_profile_parameters_declares_all_profile_fields_as_required_variables(self) -> None:
        repository = FileTemplateRepository()

        template = repository.get("profile_parameters")

        assert set(template.required_variables) == {
            "system_instruction",
            "response_style",
            "target_audience",
            "formality_level",
            "preferred_structure",
            "forbidden_phrasing_line",
            "response_length_line",
            "additional_constraints_line",
        }

    def test_memory_and_knowledge_placeholders_reference_future_stages(self) -> None:
        repository = FileTemplateRepository()

        memory = repository.get("memory_placeholder")
        knowledge = repository.get("knowledge_placeholder")

        assert "Этап 7" in memory.text
        assert "Этап 8" in knowledge.text

    def test_templates_dir_constant_points_at_seed_directory(self) -> None:
        assert DEFAULT_TEMPLATES_DIR.name == "templates"
        assert (DEFAULT_TEMPLATES_DIR / "manifest.json").exists()
