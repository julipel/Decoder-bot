"""
Разбиение документа на фрагменты (MVP: «RAG/Search... разбиение документов
на фрагменты»).

Это application-сервис, а не доменная сущность: DocumentChunker реализует
конкретный алгоритм подготовки текста к индексации (шаг конвейера
IndexDocumentUseCase), а не понятие предметной области со своим
жизненным циклом и идентичностью — в отличие от Fragment, который
остаётся в search/domain. Чистая логика без побочных эффектов — не
обращается ни к Qdrant, ни к Embedding Adapter.
"""

from __future__ import annotations


class DocumentChunker:
    """Делит текст документа на фрагменты, пригодные для эмбеддинга и поиска."""

    def __init__(self, max_chunk_size: int) -> None:
        self._max_chunk_size = max_chunk_size

    def split(self, text: str) -> list[str]:
        raise NotImplementedError
