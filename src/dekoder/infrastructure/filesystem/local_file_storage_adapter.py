from __future__ import annotations

from dekoder.application.knowledge_base.ports import FileStoragePort
from dekoder.shared.domain.identifiers import DocumentId


class LocalFileStorageAdapter(FileStoragePort):
    def __init__(self, base_path: str) -> None:
        self._base_path = base_path

    def save(self, document_id: DocumentId, content: bytes) -> None:
        raise NotImplementedError

    def read(self, document_id: DocumentId) -> bytes:
        raise NotImplementedError

    def delete(self, document_id: DocumentId) -> None:
        raise NotImplementedError
