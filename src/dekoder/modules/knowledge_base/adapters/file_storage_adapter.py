"""
Файловое хранилище оригиналов документов (docs/02, §16.4): постоянный том
(persistent volume / постоянный диск Yandex Cloud), а не файловый слой
контейнера.
"""

from __future__ import annotations

from dekoder.shared.domain.identifiers import DocumentId
from dekoder.modules.knowledge_base.application.ports import FileStoragePort


class LocalFileStorageAdapter(FileStoragePort):
    """Читает и пишет файлы на примонтированном постоянном томе."""

    def __init__(self, base_path: str) -> None:
        self._base_path = base_path

    def save(self, document_id: DocumentId, content: bytes) -> None:
        raise NotImplementedError

    def read(self, document_id: DocumentId) -> bytes:
        raise NotImplementedError

    def delete(self, document_id: DocumentId) -> None:
        raise NotImplementedError
