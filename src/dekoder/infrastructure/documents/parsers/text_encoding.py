"""
Декодирование байтов текстовых форматов (TXT/Markdown) в строку — общая
деталь `TxtParser`/`MarkdownParser` (Sprint 6, задача S6-05).

Пробует UTF-8, затем `windows-1251` (частая кодировка старых русских
`.txt`-файлов), и только затем — UTF-8 с заменой нечитаемых байтов, чтобы
разбор никогда не падал на самой кодировке (§14.2: неподдерживаемый ввод
должен приводить к понятному статусу, а не падению процесса).
"""

from __future__ import annotations


def decode_text_bytes(content: bytes) -> str:
    for encoding in ("utf-8", "windows-1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
