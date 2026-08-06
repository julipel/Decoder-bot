"""
`IndexKnowledgeDocumentUseCase` — конвейер индексации документа (Sprint 6,
задача S6-06, §14.4 «Плана реализации.md», 12 шагов).

Шаги 1-3 (приём/проверка типа и размера/checksum) поднимают
`ValidationError` НЕ создавая запись документа — как валидация входных
данных в других use case'ах (`ProcessUserMessage._validate_message_text`),
до какой-либо записи в БД. С шага 4 (запись документа уже существует)
любая ошибка — `ValidationError` парсера (§14.2 — документ без текста) или
что угодно ещё (эмбеддинги/Qdrant недоступны) — перехватывается и
становится терминальным статусом документа (`UNSUPPORTED`/`FAILED`), метод
возвращает результат, НЕ поднимает исключение (§14.12: «ошибки парсинга не
приводят к падению приложения»).

Дедупликация по checksum (ADR-6.9): повторная загрузка идентичного
содержимого находит существующую запись по `get_by_checksum` и
переиспользует её `id` — старые векторы этого документа удаляются
(`delete_by_document`) перед записью новых, дубля документа не возникает.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dekoder.application.knowledge.dto import IndexDocumentCommand, IndexDocumentResult
from dekoder.application.knowledge.pipeline import ChunkDraft, EmbeddedChunk, ParsedPage
from dekoder.application.knowledge.ports import (
    DocumentParser,
    DocumentStorage,
    EmbeddingProvider,
    KnowledgeDocumentRepository,
    TextChunker,
    VectorRepository,
)
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType
from dekoder.shared.errors import ValidationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

_EXTENSION_TO_TYPE: dict[str, DocumentType] = {
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
    ".docx": DocumentType.DOCX,
    ".pdf": DocumentType.PDF,
}

_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")


def _clean_pages(pages: list[ParsedPage]) -> list[ParsedPage]:
    """Шаг 6 «Очистка текста»: обрезает висящие пробелы по концам строк, схлопывает 3+ пустых строки до одной пустой."""
    cleaned = []
    for page in pages:
        without_trailing_spaces = "\n".join(line.rstrip() for line in page.text.splitlines())
        text = _MULTIPLE_BLANK_LINES.sub("\n\n", without_trailing_spaces).strip()
        cleaned.append(ParsedPage(number=page.number, text=text))
    return cleaned


class IndexKnowledgeDocumentUseCase:
    def __init__(
        self,
        document_repository: KnowledgeDocumentRepository,
        document_storage: DocumentStorage,
        parsers: Mapping[DocumentType, DocumentParser],
        chunker: TextChunker,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        max_file_size_bytes: int,
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._parsers = parsers
        self._chunker = chunker
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository
        self._max_file_size_bytes = max_file_size_bytes

    async def execute(self, command: IndexDocumentCommand) -> IndexDocumentResult:
        document_type = self._resolve_document_type(command.source_filename)
        self._validate_size(command.content)
        checksum = hashlib.sha256(command.content).hexdigest()

        document = await self._create_or_reuse_document(command, document_type, checksum)
        await self._document_storage.save(document.id, command.content)

        try:
            pages = _clean_pages(self._parsers[document_type].parse(command.content))
            drafts = self._chunker.chunk(pages)
            if not drafts:
                raise ValidationError(
                    message=f"Документ {document.id} не дал ни одного фрагмента после разбиения",
                    user_message="Документ не содержит контента, пригодного для индексации.",
                    code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
                )
            embedded_chunks = await self._embed(drafts)
            await self._vector_repository.delete_by_document(document.id)
            await self._vector_repository.upsert_chunks(document, embedded_chunks)
        except ValidationError as exc:
            document = await self._finalize(document, DocumentStatus.UNSUPPORTED, chunk_count=0, error=exc.user_message)
            _logger.info("knowledge_document_unsupported", document_id=str(document.id), reason=exc.message)
            return IndexDocumentResult(document=document)
        except Exception as exc:
            document = await self._finalize(document, DocumentStatus.FAILED, chunk_count=0, error=str(exc))
            _logger.error("knowledge_document_indexing_failed", document_id=str(document.id), error=str(exc))
            return IndexDocumentResult(document=document)

        document = await self._finalize(document, DocumentStatus.INDEXED, chunk_count=len(embedded_chunks), error=None)
        _logger.info("knowledge_document_indexed", document_id=str(document.id), chunk_count=len(embedded_chunks))
        return IndexDocumentResult(document=document)

    def _resolve_document_type(self, filename: str) -> DocumentType:
        suffix = Path(filename).suffix.lower()
        document_type = _EXTENSION_TO_TYPE.get(suffix)
        if document_type is None:
            supported = ", ".join(sorted(_EXTENSION_TO_TYPE))
            raise ValidationError(
                message=f"Неподдерживаемое расширение файла: {suffix!r}",
                user_message=f"Формат файла не поддерживается (поддерживаются: {supported}).",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED_FORMAT",
            )
        return document_type

    def _validate_size(self, content: bytes) -> None:
        if len(content) > self._max_file_size_bytes:
            raise ValidationError(
                message=f"Размер файла {len(content)} байт превышает лимит {self._max_file_size_bytes} байт",
                user_message="Файл слишком большой.",
                code="KNOWLEDGE_DOCUMENT_TOO_LARGE",
            )

    async def _create_or_reuse_document(
        self, command: IndexDocumentCommand, document_type: DocumentType, checksum: str
    ) -> KnowledgeDocument:
        now = datetime.now(UTC)
        existing = await self._document_repository.get_by_checksum(checksum)
        if existing is not None:
            reused = KnowledgeDocument(
                id=existing.id,
                title=command.title,
                document_type=document_type,
                source_filename=command.source_filename,
                checksum=checksum,
                status=DocumentStatus.INDEXING,
                tags=command.tags,
                description=command.description,
                chunk_count=existing.chunk_count,
                error_message=None,
                created_at=existing.created_at,
                updated_at=now,
                indexed_at=existing.indexed_at,
            )
            return await self._document_repository.update(reused)

        document = KnowledgeDocument(
            id=uuid4(),
            title=command.title,
            document_type=document_type,
            source_filename=command.source_filename,
            checksum=checksum,
            status=DocumentStatus.INDEXING,
            tags=command.tags,
            description=command.description,
            chunk_count=0,
            error_message=None,
            created_at=now,
            updated_at=now,
            indexed_at=None,
        )
        return await self._document_repository.save(document)

    async def _embed(self, drafts: list[ChunkDraft]) -> list[EmbeddedChunk]:
        vectors = await self._embedding_provider.embed_batch([draft.text for draft in drafts])
        return [
            EmbeddedChunk(
                chunk_index=index,
                text=draft.text,
                page_number=draft.page_number,
                section_title=draft.section_title,
                vector=tuple(vector),
            )
            for index, (draft, vector) in enumerate(zip(drafts, vectors, strict=True))
        ]

    async def _finalize(
        self, document: KnowledgeDocument, status: DocumentStatus, *, chunk_count: int, error: str | None
    ) -> KnowledgeDocument:
        now = datetime.now(UTC)
        finalized = KnowledgeDocument(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            source_filename=document.source_filename,
            checksum=document.checksum,
            status=status,
            tags=document.tags,
            description=document.description,
            chunk_count=chunk_count,
            error_message=error,
            created_at=document.created_at,
            updated_at=now,
            indexed_at=now if status == DocumentStatus.INDEXED else document.indexed_at,
        )
        return await self._document_repository.update(finalized)
