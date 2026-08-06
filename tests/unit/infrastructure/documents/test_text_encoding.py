"""Тесты `decode_text_bytes` (Sprint 6, задача S6-05) — общий декодер `TxtParser`/`MarkdownParser`."""

from __future__ import annotations

from dekoder.infrastructure.documents.parsers.text_encoding import decode_text_bytes


class TestDecodeTextBytes:
    def test_decodes_utf8(self) -> None:
        assert decode_text_bytes("Привет!".encode()) == "Привет!"

    def test_decodes_windows_1251(self) -> None:
        assert decode_text_bytes("Привет!".encode("windows-1251")) == "Привет!"

    def test_falls_back_to_utf8_with_replacement_when_neither_encoding_matches(self) -> None:
        # 0x98 не определён ни в windows-1251, ни как валидный старт-байт UTF-8.
        result = decode_text_bytes(b"\x98")

        assert result == "�"
