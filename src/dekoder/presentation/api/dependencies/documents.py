"""
Per-request сборка документных admin use case'ов (Sprint 8, задача
S8-05, ADR-8.4) — единственное место в `presentation/`, которому
разрешено импортировать `bootstrap/knowledge_container.py` и знать про
`AsyncSession`/`session_scope()`.

`get_admin_session` — yield-зависимость: открывает `session_scope()` на
время одного HTTP-запроса, тем же приёмом, что `scripts/index_document.py`
держит `session_scope()` открытой на весь `use_case.execute()`. FastAPI
сам корректно раскручивает цепочку `yield`-зависимостей — commit/rollback
`session_scope()` происходит уже после того, как обработчик роута вернул
ответ (тело роута выполняется внутри контекста открытой сессии).

`IndexKnowledgeDocumentUseCase`/`DeleteKnowledgeDocumentUseCase`/
`ReindexKnowledgeDocumentUseCase` намеренно не входят в
`ApplicationContainer` (ADR-8.4) — держат сессию открытой на время
многосекундного внешнего конвейера (парсинг -> chunking -> embeddings ->
Qdrant), что не вписывается в короткую транзакционную модель
`ConversationRepositoriesFactory`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dekoder.application.knowledge.use_cases.delete_document import DeleteKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.get_document import GetKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.index_document import IndexKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.list_documents import ListKnowledgeDocumentsUseCase
from dekoder.application.knowledge.use_cases.reindex_document import ReindexKnowledgeDocumentUseCase
from dekoder.bootstrap.application import (
    get_db_session_factory,
    get_embedding_http_client,
    get_qdrant_client,
    get_settings,
)
from dekoder.bootstrap.knowledge_container import (
    build_delete_document_use_case,
    build_get_document_use_case,
    build_index_document_use_case,
    build_list_documents_use_case,
    build_reindex_document_use_case,
)
from dekoder.infrastructure.persistence.session import session_scope
from dekoder.shared.config import Settings


async def get_admin_session(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_db_session_factory),
) -> AsyncIterator[AsyncSession]:
    async with session_scope(session_factory) as session:
        yield session


@dataclass(frozen=True)
class DocumentUseCases:
    index: IndexKnowledgeDocumentUseCase
    delete: DeleteKnowledgeDocumentUseCase
    list_all: ListKnowledgeDocumentsUseCase
    get: GetKnowledgeDocumentUseCase
    reindex: ReindexKnowledgeDocumentUseCase


async def get_document_use_cases(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_admin_session),
    embedding_http_client: httpx.AsyncClient = Depends(get_embedding_http_client),
    qdrant_client: AsyncQdrantClient = Depends(get_qdrant_client),
) -> DocumentUseCases:
    return DocumentUseCases(
        index=build_index_document_use_case(settings, session, embedding_http_client, qdrant_client),
        delete=build_delete_document_use_case(settings, session, qdrant_client),
        list_all=build_list_documents_use_case(session),
        get=build_get_document_use_case(session),
        reindex=build_reindex_document_use_case(settings, session, embedding_http_client, qdrant_client),
    )
