"""
Composition root конвейера индексации базы знаний (Sprint 6, задача
S6-09) — отдельный от `bootstrap/container.py` (`ApplicationContainer`,
задача S2-06): индексация НЕ часть диалогового контейнера api/telegram-bot
(ADR-6.4/6.6) — у неё свой вызывающий процесс, `scripts/index_document.py`,
не FastAPI/Telegram. Полноценный защищённый admin REST API для
индексации — Этап 10, отдельный будущий спринт (ADR-6.6).

`build_index_document_use_case`/`build_delete_document_use_case`
принимают уже открытую `AsyncSession` (тем же приёмом, что и
`bootstrap/repositories.py::build_memory_repository` и т.п.) — границей
транзакции управляет вызывающий код (`scripts/index_document.py`, через
`session_scope()`), не этот модуль.

С задачи S8-04 (Sprint 8, ADR-8.4/8.5/8.6) модуль дополнен тремя новыми
билдерами — `build_list_documents_use_case`/`build_get_document_use_case`
(тонкие обёртки чтения над `KnowledgeDocumentRepository`) и
`build_reindex_document_use_case` (переиспользует
`build_index_document_use_case` внутри себя, не дублирует сборку
конвейера индексации). Их вызывают одновременно REST-слой
(`presentation/api/dependencies/documents.py`, S8-05) и CLI
(`scripts/index_document.py`, S8-10) — единая точка истины сборки для
обоих интерфейсов.
"""

from __future__ import annotations

import httpx
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.application.knowledge.ports import DocumentParser
from dekoder.application.knowledge.use_cases.delete_document import DeleteKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.get_document import GetKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.index_document import IndexKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.list_documents import ListKnowledgeDocumentsUseCase
from dekoder.application.knowledge.use_cases.reindex_document import ReindexKnowledgeDocumentUseCase
from dekoder.bootstrap.repositories import build_knowledge_document_repository
from dekoder.domain.knowledge.value_objects import DocumentType
from dekoder.infrastructure.documents.chunking.structural_chunker import StructuralChunker
from dekoder.infrastructure.documents.parsers.docx_parser import DocxParser
from dekoder.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from dekoder.infrastructure.documents.parsers.pdf_parser import PdfParser
from dekoder.infrastructure.documents.parsers.txt_parser import TxtParser
from dekoder.infrastructure.embeddings.openai_embedding_provider import OpenAiEmbeddingProvider
from dekoder.infrastructure.filesystem.local_document_storage import LocalDocumentStorageAdapter
from dekoder.infrastructure.qdrant.vector_repository import QdrantVectorRepository
from dekoder.shared.config import Settings

_PARSERS: dict[DocumentType, DocumentParser] = {
    DocumentType.TXT: TxtParser(),
    DocumentType.MARKDOWN: MarkdownParser(),
    DocumentType.DOCX: DocxParser(),
    DocumentType.PDF: PdfParser(),
}


def build_index_document_use_case(
    settings: Settings,
    session: AsyncSession,
    openai_http_client: httpx.AsyncClient,
    qdrant_client: AsyncQdrantClient,
) -> IndexKnowledgeDocumentUseCase:
    document_repository = build_knowledge_document_repository(session)
    document_storage = LocalDocumentStorageAdapter(settings.knowledge.storage_path)
    embedding_provider = OpenAiEmbeddingProvider(
        client=openai_http_client,
        api_key=settings.openai.api_key.get_secret_value(),
        model=settings.openai.embedding_model,
    )
    vector_repository = QdrantVectorRepository(client=qdrant_client, collection_name=settings.qdrant.collection_name)
    chunker = StructuralChunker(
        chunk_size=settings.knowledge.chunk_size,
        chunk_overlap=settings.knowledge.chunk_overlap,
    )
    return IndexKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        parsers=_PARSERS,
        chunker=chunker,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        max_file_size_bytes=settings.knowledge.max_file_size_bytes,
    )


def build_delete_document_use_case(
    settings: Settings,
    session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
) -> DeleteKnowledgeDocumentUseCase:
    document_repository = build_knowledge_document_repository(session)
    document_storage = LocalDocumentStorageAdapter(settings.knowledge.storage_path)
    vector_repository = QdrantVectorRepository(client=qdrant_client, collection_name=settings.qdrant.collection_name)
    return DeleteKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        vector_repository=vector_repository,
    )


def build_list_documents_use_case(session: AsyncSession) -> ListKnowledgeDocumentsUseCase:
    """Собирает `ListKnowledgeDocumentsUseCase` поверх переданной `AsyncSession` (Sprint 8, задача S8-04)."""
    document_repository = build_knowledge_document_repository(session)
    return ListKnowledgeDocumentsUseCase(document_repository=document_repository)


def build_get_document_use_case(session: AsyncSession) -> GetKnowledgeDocumentUseCase:
    """Собирает `GetKnowledgeDocumentUseCase` поверх переданной `AsyncSession` (Sprint 8, задача S8-04)."""
    document_repository = build_knowledge_document_repository(session)
    return GetKnowledgeDocumentUseCase(document_repository=document_repository)


def build_reindex_document_use_case(
    settings: Settings,
    session: AsyncSession,
    openai_http_client: httpx.AsyncClient,
    qdrant_client: AsyncQdrantClient,
) -> ReindexKnowledgeDocumentUseCase:
    """
    Собирает `ReindexKnowledgeDocumentUseCase` (Sprint 8, задача S8-04,
    ADR-8.6) — переиспользует `build_index_document_use_case` внутри
    себя, не дублирует сборку конвейера индексации.
    """
    document_repository = build_knowledge_document_repository(session)
    document_storage = LocalDocumentStorageAdapter(settings.knowledge.storage_path)
    index_use_case = build_index_document_use_case(settings, session, openai_http_client, qdrant_client)
    return ReindexKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        index_use_case=index_use_case,
    )
