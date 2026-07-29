"""
Кросс-модульные Value Objects (docs/versions/04, §5): не opaque-идентификаторы,
поэтому вынесены отдельно от identifiers.py — GenerationType закрытый enum,
ContentType открытый строковый VO, Prompt — структурный результат Prompt Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


class GenerationType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


ContentType = NewType("ContentType", str)


@dataclass(frozen=True)
class Prompt:
    """Итоговая инструкция Prompt Engine — не хранится, одноразовое значение одного вызова (04, §5)."""

    text: str | None
    image_request: dict[str, str] | None = None
