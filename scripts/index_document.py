"""
CLI-скрипт индексации/удаления документов базы знаний (Sprint 6, задача
S6-09, ADR-6.6): единственный способ запустить конвейер индексации в
Sprint 6 — вызывает use cases напрямую через `bootstrap/
knowledge_container.py`, без REST/auth-слоя. Полноценный защищённый
admin API — Этап 10, отдельный будущий спринт.

Использование:
    python scripts/index_document.py index <файл> [--title ...] [--tags a,b,c] [--description ...]
    python scripts/index_document.py delete <document_id>
    python scripts/index_document.py list
    python scripts/index_document.py reindex <document_id>

В отличие от `bootstrap/application.py`/`telegram_main.py`,
`ensure_collection` здесь fail-fast (не перехватывается) — индексация без
доступного Qdrant бессмысленна, в то время как обычный диалог должен
продолжать работать без RAG (см. `bootstrap/application.py`).

С задачи S8-10 (Sprint 8, ADR-8.11) скрипт не переименован (churn без
функциональной пользы) и дополнен подкомандами `list`/`reindex` —
переиспользуют те же билдеры `bootstrap/knowledge_container.py`
(`build_list_documents_use_case`/`build_reindex_document_use_case`,
S8-04), что и REST-слой (`presentation/api/routes/admin_documents.py`,
S8-05) — единая точка истины сборки для обоих интерфейсов. `list` не
трогает Qdrant вообще (только чтение метаданных из БД, без
`ensure_collection`/`build_qdrant_client`); `reindex` — тот же каркас,
что `index` (fail-fast `ensure_collection`, второй `httpx.AsyncClient`
для эмбеддингов).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

import httpx

from dekoder.application.knowledge.dto import IndexDocumentCommand
from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.bootstrap.knowledge_container import (
    build_delete_document_use_case,
    build_index_document_use_case,
    build_list_documents_use_case,
    build_reindex_document_use_case,
)
from dekoder.domain.knowledge.value_objects import DocumentStatus
from dekoder.infrastructure.persistence.session import session_scope
from dekoder.infrastructure.qdrant.client import build_qdrant_client, ensure_collection
from dekoder.shared.config import Settings
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


async def _run_index(
    settings: Settings,
    *,
    file_path: Path,
    content: bytes,
    title: str | None,
    tags: tuple[str, ...],
    description: str | None,
) -> int:
    db_engine, db_session_factory = await init_database(settings)
    qdrant_client = build_qdrant_client(settings.qdrant)
    try:
        await ensure_collection(qdrant_client, settings.qdrant)
        # timeout переиспользует LLMSettings.timeout — см. bootstrap/application.py.
        async with (
            httpx.AsyncClient(base_url=settings.openai.base_url, timeout=settings.llm.timeout) as openai_http_client,
            session_scope(db_session_factory) as session,
        ):
            use_case = build_index_document_use_case(settings, session, openai_http_client, qdrant_client)
            try:
                result = await use_case.execute(
                    IndexDocumentCommand(
                        title=title or file_path.stem,
                        source_filename=file_path.name,
                        content=content,
                        tags=tags,
                        description=description,
                    )
                )
            except DekoderError as error:
                # Только шаги 1-3 (тип/размер) поднимают исключение — с
                # шага 4 (запись документа уже создана) use case сам
                # переводит любую ошибку в статус документа и возвращает
                # результат, не поднимает (см. докстринг
                # IndexKnowledgeDocumentUseCase).
                print(f"Документ отклонён: {error.user_message}", file=sys.stderr)
                return 2
    finally:
        await qdrant_client.close()
        await dispose_database(db_engine)

    document = result.document
    print(f"document_id={document.id} status={document.status.value} chunk_count={document.chunk_count}")
    if document.error_message:
        print(f"error: {document.error_message}", file=sys.stderr)
    return 0 if document.status is DocumentStatus.INDEXED else 1


async def _run_delete(args: argparse.Namespace, settings: Settings) -> int:
    try:
        document_id = UUID(args.document_id)
    except ValueError:
        print(f"Некорректный document_id: {args.document_id!r}", file=sys.stderr)
        return 2

    db_engine, db_session_factory = await init_database(settings)
    qdrant_client = build_qdrant_client(settings.qdrant)
    try:
        await ensure_collection(qdrant_client, settings.qdrant)
        async with session_scope(db_session_factory) as session:
            use_case = build_delete_document_use_case(settings, session, qdrant_client)
            await use_case.execute(document_id)
    finally:
        await qdrant_client.close()
        await dispose_database(db_engine)

    print(f"document_id={document_id} deleted")
    return 0


async def _run_list(settings: Settings) -> int:
    """`list` не трогает Qdrant — только чтение метаданных документов из БД (build_list_documents_use_case, S8-04)."""
    db_engine, db_session_factory = await init_database(settings)
    try:
        async with session_scope(db_session_factory) as session:
            use_case = build_list_documents_use_case(session)
            documents = await use_case.execute()
    finally:
        await dispose_database(db_engine)

    if not documents:
        print("Документов нет.")
        return 0

    print(f"{'id':36}  {'status':12}  {'chunks':>6}  {'updated_at':26}  title")
    for document in documents:
        print(
            f"{document.id}  {document.status.value:12}  {document.chunk_count:>6}  "
            f"{document.updated_at.isoformat():26}  {document.title}"
        )
    return 0


async def _run_reindex(args: argparse.Namespace, settings: Settings) -> int:
    try:
        document_id = UUID(args.document_id)
    except ValueError:
        print(f"Некорректный document_id: {args.document_id!r}", file=sys.stderr)
        return 2

    db_engine, db_session_factory = await init_database(settings)
    qdrant_client = build_qdrant_client(settings.qdrant)
    try:
        await ensure_collection(qdrant_client, settings.qdrant)
        async with (
            httpx.AsyncClient(base_url=settings.openai.base_url, timeout=settings.llm.timeout) as openai_http_client,
            session_scope(db_session_factory) as session,
        ):
            use_case = build_reindex_document_use_case(settings, session, openai_http_client, qdrant_client)
            result = await use_case.execute(document_id)
    finally:
        await qdrant_client.close()
        await dispose_database(db_engine)

    if result is None:
        print(f"Документ не найден: {document_id}", file=sys.stderr)
        return 2

    document = result.document
    print(f"document_id={document.id} status={document.status.value} chunk_count={document.chunk_count}")
    if document.error_message:
        print(f"error: {document.error_message}", file=sys.stderr)
    return 0 if document.status is DocumentStatus.INDEXED else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Индексация/удаление документов базы знаний (Sprint 6, S6-09).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Загрузить и проиндексировать документ.")
    index_parser.add_argument("file", help="Путь к файлу (.txt/.md/.docx/.pdf).")
    index_parser.add_argument("--title", default=None, help="Заголовок документа (по умолчанию — имя файла).")
    index_parser.add_argument("--tags", default=None, help="Теги через запятую.")
    index_parser.add_argument("--description", default=None, help="Краткое описание документа.")

    delete_parser = subparsers.add_parser("delete", help="Удалить документ и его векторы.")
    delete_parser.add_argument("document_id", help="UUID документа.")

    subparsers.add_parser("list", help="Показать список всех документов каталога (Sprint 8, S8-10).")

    reindex_parser = subparsers.add_parser(
        "reindex", help="Переиндексировать уже загруженный документ без повторной загрузки файла (Sprint 8, S8-10)."
    )
    reindex_parser.add_argument("document_id", help="UUID документа.")

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    settings = Settings()
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )

    if args.command == "index":
        file_path = Path(args.file)
        if not file_path.is_file():
            print(f"Файл не найден: {file_path}", file=sys.stderr)
            sys.exit(2)
        content = file_path.read_bytes()
        tags = tuple(tag.strip() for tag in args.tags.split(",") if tag.strip()) if args.tags else ()

        _logger.info("knowledge_document_indexing_started", file=str(file_path))
        exit_code = asyncio.run(
            _run_index(
                settings,
                file_path=file_path,
                content=content,
                title=args.title,
                tags=tags,
                description=args.description,
            )
        )
    elif args.command == "delete":
        _logger.info("knowledge_document_deletion_started", document_id=args.document_id)
        exit_code = asyncio.run(_run_delete(args, settings))
    elif args.command == "list":
        exit_code = asyncio.run(_run_list(settings))
    else:
        _logger.info("knowledge_document_reindex_cli_started", document_id=args.document_id)
        exit_code = asyncio.run(_run_reindex(args, settings))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
