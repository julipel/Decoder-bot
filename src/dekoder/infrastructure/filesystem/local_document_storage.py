"""
`LocalDocumentStorageAdapter` — реализация `DocumentStorage` (Sprint 6,
задача S6-05) поверх локальной файловой системы: исходные байты
документа, ключ — `document_id`.

Файловый I/O — блокирующий; каждый вызов уходит в `asyncio.to_thread`,
чтобы не задерживать event loop (§18.5 «Плана реализации.md» — «отсутствие
блокировки event loop»), тем же приёмом, что синхронный `DocumentParser`/
`TextChunker` вызываются из `IndexKnowledgeDocumentUseCase` (задача S6-06).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from dekoder.shared.errors import InfrastructureError


class LocalDocumentStorageAdapter:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)

    async def save(self, document_id: UUID, content: bytes) -> None:
        path = self._path_for(document_id)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(_write)

    async def read(self, document_id: UUID) -> bytes:
        path = self._path_for(document_id)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise InfrastructureError(
                message=f"Не удалось прочитать файл документа {document_id}: {exc}",
                user_message="Не удалось прочитать документ, попробуйте позже.",
                code="KNOWLEDGE_DOCUMENT_FILE_READ_FAILED",
                cause=exc,
            ) from exc

    async def delete(self, document_id: UUID) -> None:
        """Идемпотентна: отсутствующий файл — не ошибка (§14.6 — тот же контракт, что и у порта)."""

        def _delete() -> None:
            self._path_for(document_id).unlink(missing_ok=True)

        await asyncio.to_thread(_delete)

    def _path_for(self, document_id: UUID) -> Path:
        return self._base_path / str(document_id)
