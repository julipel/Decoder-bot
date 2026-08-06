"""
Минимальный «ручной» строитель PDF для тестов `PdfParser`
(`tests/unit/infrastructure/documents/test_pdf_parser.py`).

Никакая тяжёлая библиотека генерации PDF (reportlab/fpdf2) не является
зависимостью проекта — вместо неё здесь собирается наименьший корректный
PDF-документ (объекты `Catalog`/`Pages`/`Page`/`Contents`/`Font` + таблица
xref) вручную, байт в байт, с реальным текстовым слоем, извлекаемым
`pypdf`. Только для тестов, не часть `src/`.
"""

from __future__ import annotations

_HELVETICA_FONT_OBJ = 100


def build_minimal_pdf(pages: list[str]) -> bytes:
    """Собирает PDF из одной или нескольких страниц; каждая строка `pages[i]` становится текстом страницы `i + 1`."""
    objects: dict[int, bytes] = {}
    page_object_ids = list(range(3, 3 + len(pages)))
    content_object_ids = list(range(3 + len(pages), 3 + 2 * len(pages)))

    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()

    for page_id, content_id in zip(page_object_ids, content_object_ids, strict=True):
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {_HELVETICA_FONT_OBJ} 0 R >> >> "
            f"/MediaBox [0 0 612 792] /Contents {content_id} 0 R >>"
        ).encode()

    for content_id, text in zip(content_object_ids, pages, strict=True):
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream = f"BT /F1 24 Tf 72 700 Td ({escaped}) Tj ET".encode()
        objects[content_id] = b"<< /Length " + str(len(stream)).encode() + b" >>stream\n" + stream + b"\nendstream"

    objects[_HELVETICA_FONT_OBJ] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    return _assemble(objects)


def _assemble(objects: dict[int, bytes]) -> bytes:
    ordered_ids = sorted(objects)
    max_id = ordered_ids[-1]

    body = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for object_id in ordered_ids:
        offsets[object_id] = len(body)
        body += f"{object_id} 0 obj".encode() + objects[object_id] + b"endobj\n"

    xref_offset = len(body)
    body += f"xref\n0 {max_id + 1}\n".encode()
    body += b"0000000000 65535 f \n"
    for object_id in range(1, max_id + 1):
        offset = offsets.get(object_id, 0)
        body += f"{offset:010d} 00000 n \n".encode()

    body += f"trailer<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return body
