"""
Порты сервиса поиска (docs/02, §7 и явное требование: «RAG зависит от
EmbeddingPort и VectorStorePort, но не от конкретных провайдеров и
Qdrant-клиента»).

EmbeddingPort размещён здесь, а не в отдельном модуле верхнего уровня,
потому что Embedding Adapter — часть модуля RAG/Search по заданному
списку модулей; используется только внутри search, наружу не отдаётся.
"""

from __future__ import annotations

from typing import Protocol

from dekoder.modules.search.domain.fragment import Fragment, FragmentSourceType
from dekoder.shared.domain.identifiers import CaseId, DocumentId


class KnowledgeSearchPort(Protocol):
    """Семантический поиск фрагментов документов/кейсов (используется AI Core)."""

    def search(self, query: str, top_k: int) -> list[Fragment]: ...


class IndexingPort(Protocol):
    """Индексация/переиндексация/удаление из индекса (используется Admin)."""

    def index_document(self, document_id: DocumentId) -> None: ...

    def index_case(self, case_id: CaseId) -> None: ...

    def remove_from_index(self, source_type: FragmentSourceType, source_id: str) -> None: ...


class EmbeddingPort(Protocol):
    """
    Векторное представление текста. Активный провайдер задаётся независимо
    от LLMPort — EMBEDDING_PROVIDER/EMBEDDING_MODEL (docs/02, §16.2).
    """

    def embed(self, text: str) -> list[float]: ...


class VectorStorePort(Protocol):
    """Абстракция над векторным хранилищем (в MVP — Qdrant), скрывающая клиент Qdrant от use case'ов."""

    def upsert(self, fragments: list[Fragment], vectors: list[list[float]]) -> None: ...

    def query(self, vector: list[float], top_k: int) -> list[Fragment]: ...

    def delete_by_source(self, source_type: FragmentSourceType, source_id: str) -> None: ...
