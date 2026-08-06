"""
Порты подсистемы базы знаний (Sprint 6, §14.6 «Плана реализации.md»):
`KnowledgeDocumentRepository`, `DocumentStorage`, `DocumentParser`,
`TextChunker`, `EmbeddingProvider`, `VectorRepository`,
`KnowledgeSearchService` — каждый отвечает только за одну область.

Стиль — как у `MemoryRepository`/`ProfileRepository`: `Protocol` +
`@runtime_checkable`, только доменные типы и типы стандартной библиотеки
в сигнатурах, ничего из SQLAlchemy/Qdrant/httpx.

`KnowledgeDocumentRepository` НЕ входит в `ConversationRepositories`
(в отличие от `ProfileRepository`/`MemoryRepository`, ADR-3.3/5.5) — база
знаний не участвует в транзакции `ProcessUserMessage` (`process_user_message.
py`, ADR-6.4), ей пользуется только конвейер индексации
(`IndexKnowledgeDocumentUseCase`/`DeleteKnowledgeDocumentUseCase`,
запускаемый `scripts/index_document.py`, задача S6-09).

`KnowledgeSearchService` — единственный порт этого модуля, который
`ProcessUserMessage` действительно вызывает (ADR-6.4): внедряется в его
конструктор отдельным параметром, как `LLMProvider`, не как часть
`ConversationRepositories` — поиск требует внешних HTTP-вызовов
(эмбеддинг + Qdrant), а не только чтения БД, поэтому не может жить внутри
короткой DB-транзакции наравне с `profiles`/`memory`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from dekoder.application.knowledge.pipeline import ChunkDraft, EmbeddedChunk, ParsedPage
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.search import SearchResult


@runtime_checkable
class KnowledgeDocumentRepository(Protocol):
    """Метаданные документов (`knowledge_documents`, задача S6-04) — без текста/векторов фрагментов (ADR-6.2)."""

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """Сохраняет НОВУЮ запись документа."""
        ...

    async def get_by_id(self, document_id: UUID) -> KnowledgeDocument | None: ...

    async def get_by_checksum(self, checksum: str) -> KnowledgeDocument | None:
        """
        Возвращает документ с таким же `checksum`, если он уже
        загружался — точка дедупликации (ADR-6.9): повторная загрузка
        идентичного содержимого обновляет эту запись, а не создаёт
        дубликат.
        """
        ...

    async def update(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """
        Обновляет существующую запись целиком по `document.id` (статус,
        `chunk_count`, `indexed_at`, `error_message` меняются вместе на
        каждом шаге конвейера индексации — узкие `update_status`-подобные
        методы не оправданы для одной сущности с несколькими полями,
        меняющимися синхронно).
        """
        ...

    async def delete(self, document_id: UUID) -> None:
        """Удаляет запись документа. Идемпотентна: отсутствующий `document_id` — 0 удалённых строк, не ошибка."""
        ...


@runtime_checkable
class DocumentStorage(Protocol):
    """Хранилище исходных байт документа (§14.6) — отдельно от Qdrant/SQL, задел на переиндексацию без перезагрузки."""

    async def save(self, document_id: UUID, content: bytes) -> None: ...

    async def read(self, document_id: UUID) -> bytes: ...

    async def delete(self, document_id: UUID) -> None:
        """Идемпотентна: отсутствующий файл — не ошибка (документ мог быть загружен, но так и не проиндексирован)."""
        ...


@runtime_checkable
class DocumentParser(Protocol):
    """
    Извлечение текста одного формата (`TxtParser`/`MarkdownParser`/
    `DocxParser`/`PdfParser`, задача S6-05). Синхронный — разбор файла не
    требует сетевых вызовов.
    """

    def parse(self, content: bytes) -> list[ParsedPage]:
        """
        Возвращает список «страниц» (§14.5). Документ без извлекаемого
        текста (например, PDF из одних картинок) — не пустой список, а
        `dekoder.shared.errors.ValidationError` (§14.2: «должны возвращать
        понятную ошибку или статус «не поддерживается»») — вызывающий
        use case превращает её в `DocumentStatus.UNSUPPORTED`.
        """
        ...


@runtime_checkable
class TextChunker(Protocol):
    """Разбиение извлечённого текста на фрагменты по структурным/смысловым границам (§14.4, шаг 7)."""

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkDraft]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Провайдер эмбеддингов (только OpenAI в Sprint 6, ADR-6.3) — асинхронный, обращается к внешнему API."""

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Возвращает по одному вектору на каждый элемент `texts`, в том же порядке."""
        ...


@runtime_checkable
class VectorRepository(Protocol):
    """Хранилище векторов фрагментов (Qdrant, ADR-6.2) — единственный источник истины по тексту/векторам фрагментов."""

    async def upsert_chunks(self, document: KnowledgeDocument, chunks: Sequence[EmbeddedChunk]) -> None:
        """Записывает фрагменты документа. Не удаляет старые точки этого документа — это отдельный шаг (ADR-6.9)."""
        ...

    async def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
        min_score: float,
        document_ids: Sequence[UUID] | None = None,
        tags: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        """Семантический поиск (§14.7). Пустой список — штатный исход (нет результата выше порога), не исключение."""
        ...

    async def delete_by_document(self, document_id: UUID) -> None:
        """Удаляет ВСЕ точки указанного документа. Идемпотентна: документ без точек — не ошибка."""
        ...


@runtime_checkable
class KnowledgeSearchService(Protocol):
    """
    Порт, который `ProcessUserMessage` вызывает напрямую (ADR-6.4) — без
    отдельного use-case класса или коллаборатора: композиция
    `EmbeddingProvider` + `VectorRepository` за настройками по умолчанию
    (`SemanticSearchService`, задача S6-07) — тот же уровень абстракции,
    что и `LLMProvider`.
    """

    async def search(self, query_text: str) -> Sequence[SearchResult]:
        """
        Возвращает релевантные фрагменты для `query_text` с параметрами
        по умолчанию из `KnowledgeSettings` (`limit`/`min_relevance_score`)
        — без фильтров по документам/тегам, которые нужны только
        административному поиску (`VectorRepository.search` их
        поддерживает напрямую, этот порт — нет, YAGNI).
        """
        ...
