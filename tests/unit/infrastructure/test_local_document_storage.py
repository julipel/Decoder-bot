"""Тесты `LocalDocumentStorageAdapter` (Sprint 6, задача S6-05) — на временном каталоге `tmp_path`."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from dekoder.infrastructure.filesystem.local_document_storage import LocalDocumentStorageAdapter
from dekoder.shared.errors import InfrastructureError


class TestLocalDocumentStorageAdapter:
    async def test_save_then_read_roundtrips_content(self, tmp_path: Path) -> None:
        storage = LocalDocumentStorageAdapter(base_path=str(tmp_path))
        document_id = uuid4()

        await storage.save(document_id, b"document bytes")
        content = await storage.read(document_id)

        assert content == b"document bytes"

    async def test_save_creates_base_directory_if_missing(self, tmp_path: Path) -> None:
        nested_path = tmp_path / "nested" / "storage"
        storage = LocalDocumentStorageAdapter(base_path=str(nested_path))
        document_id = uuid4()

        await storage.save(document_id, b"content")

        assert (nested_path / str(document_id)).exists()

    async def test_read_missing_file_raises_infrastructure_error(self, tmp_path: Path) -> None:
        storage = LocalDocumentStorageAdapter(base_path=str(tmp_path))

        with pytest.raises(InfrastructureError) as exc_info:
            await storage.read(uuid4())

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_FILE_READ_FAILED"

    async def test_delete_removes_file(self, tmp_path: Path) -> None:
        storage = LocalDocumentStorageAdapter(base_path=str(tmp_path))
        document_id = uuid4()
        await storage.save(document_id, b"content")

        await storage.delete(document_id)

        assert not (tmp_path / str(document_id)).exists()

    async def test_delete_missing_file_is_idempotent(self, tmp_path: Path) -> None:
        storage = LocalDocumentStorageAdapter(base_path=str(tmp_path))

        await storage.delete(uuid4())  # не должно поднимать исключение
