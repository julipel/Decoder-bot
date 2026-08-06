"""
Тесты разбора аргументов `scripts/index_document.py` (Sprint 6, задача
S6-09) — только `_build_parser()`, чистая функция без I/O. Полная
проверка `_run_index`/`_run_delete` (реальные БД/Qdrant/OpenAI) —
Docker-based E2E проверка Sprint 6 (задача S6-11), не unit-тест: эти
функции жёстко связаны с `bootstrap/database.py::init_database`/
`infrastructure/qdrant/client.py`, подменять их fake-объектами здесь
означало бы тестировать моки, а не реальную интеграцию.
"""

from __future__ import annotations

import pytest
from scripts.index_document import _build_parser


class TestIndexSubcommand:
    def test_parses_required_file_argument(self) -> None:
        args = _build_parser().parse_args(["index", "document.txt"])

        assert args.command == "index"
        assert args.file == "document.txt"
        assert args.title is None
        assert args.tags is None
        assert args.description is None

    def test_parses_optional_arguments(self) -> None:
        args = _build_parser().parse_args(
            [
                "index",
                "document.pdf",
                "--title",
                "Заголовок",
                "--tags",
                "a,b, c",
                "--description",
                "Описание",
            ]
        )

        assert args.title == "Заголовок"
        assert args.tags == "a,b, c"
        assert args.description == "Описание"


class TestDeleteSubcommand:
    def test_parses_document_id_argument(self) -> None:
        args = _build_parser().parse_args(["delete", "11111111-1111-1111-1111-111111111111"])

        assert args.command == "delete"
        assert args.document_id == "11111111-1111-1111-1111-111111111111"


class TestMissingSubcommand:
    def test_requires_a_subcommand(self) -> None:
        with pytest.raises(SystemExit):
            _build_parser().parse_args([])
