"""
`FileTemplateRepository` — файловая реализация `PromptTemplateRepository`
(Sprint 4, задача S4-04, ADR-4.2).

Читает манифест (`templates/manifest.json`) и по одному текстовому файлу
на шаблон из `infrastructure/prompts/templates/` — ОДИН РАЗ при
построении репозитория (`__init__`), не на каждый запрос (ADR-4.2:
«файлы читаются один раз при построении репозитория... не
перечитываются на каждый запрос»). Никакого обращения к БД/Alembic/HTTP.

Подстановка переменных внутри самих шаблонов — `string.Template`
(`application/prompt/services/prompt_builder.py`, задача S4-05), не
здесь: этот модуль только загружает шаблоны как данные (`PromptTemplate.
text` — ещё не подставленный текст).

Ошибка при отсутствующем файле/шаблоне — `shared.errors.
InfrastructureError` (не голый `OSError`/`KeyError`/`json.JSONDecodeError`)
с понятным сообщением, называющим путь/имя — по прецеденту остальных
инфраструктурных адаптеров проекта.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from dekoder.domain.prompt.entities import PromptTemplate, PromptTemplateStatus
from dekoder.shared.errors import InfrastructureError

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
"""Каталог сид-шаблонов по умолчанию — рядом с этим модулем (`infrastructure/prompts/templates/`)."""

_MANIFEST_FILENAME = "manifest.json"


class FileTemplateRepository:
    """
    Реализация `PromptTemplateRepository` (`application/prompt/ports.py`)
    поверх плоских текстовых файлов + JSON-манифеста — структурное
    соответствие протоколу (`@runtime_checkable`), без явного
    наследования, по стилю `SQLAlchemyProfileRepository`/
    `SQLAlchemyUserRepository` (`infrastructure/persistence/`).

    `get()`/`list_all()` — синхронные, без I/O: вся файловая работа
    выполнена в `__init__`, результат закэширован в `dict[str,
    PromptTemplate]`. Это позволяет `PromptBuilder.build()` (ADR-4.1/4.8)
    оставаться синхронным и не выполнять I/O на каждый вызов.
    """

    def __init__(self, templates_dir: Path | None = None) -> None:
        directory = templates_dir if templates_dir is not None else DEFAULT_TEMPLATES_DIR
        self._templates: dict[str, PromptTemplate] = self._load(directory)

    def get(self, name: str) -> PromptTemplate:
        try:
            return self._templates[name]
        except KeyError as error:
            known = ", ".join(sorted(self._templates)) or "<пусто>"
            raise InfrastructureError(
                message=f"Шаблон промпта '{name}' не найден. Известные шаблоны: {known}.",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
                metadata={"template_name": name},
            ) from error

    def list_all(self) -> Sequence[PromptTemplate]:
        return list(self._templates.values())

    @staticmethod
    def _load(directory: Path) -> dict[str, PromptTemplate]:
        manifest_path = directory / _MANIFEST_FILENAME
        try:
            manifest_raw = manifest_path.read_text(encoding="utf-8")
        except OSError as error:
            raise InfrastructureError(
                message=f"Не удалось прочитать манифест шаблонов промпта: {manifest_path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        try:
            entries: list[dict[str, Any]] = json.loads(manifest_raw)
        except json.JSONDecodeError as error:
            raise InfrastructureError(
                message=f"Манифест шаблонов промпта повреждён (невалидный JSON): {manifest_path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        templates: dict[str, PromptTemplate] = {}
        for entry in entries:
            template = FileTemplateRepository._build_template(directory, entry)
            templates[template.id] = template
        return templates

    @staticmethod
    def _build_template(directory: Path, entry: dict[str, Any]) -> PromptTemplate:
        text_path = directory / entry["text_file"]
        try:
            # `.rstrip("\n")` — устраняет разночтения из-за завершающего
            # перевода строки в текстовом файле (зависит от редактора/ОС),
            # не трогая остальные пробельные символы тела шаблона.
            text = text_path.read_text(encoding="utf-8").rstrip("\n")
        except OSError as error:
            raise InfrastructureError(
                message=f"Не удалось прочитать файл шаблона промпта: {text_path}",
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                cause=error,
            ) from error

        return PromptTemplate(
            id=entry["id"],
            name=entry["name"],
            version=entry["version"],
            purpose=entry["purpose"],
            text=text,
            required_variables=tuple(entry["required_variables"]),
            status=PromptTemplateStatus(entry["status"]),
            updated_at=datetime.fromisoformat(entry["updated_at"]),
        )
