"""
Источник текущего времени (docs/versions/05, §8): кросс-модульная утилита,
не привязанная ни к одному компоненту `02` — используется, например, при
проставлении `created_at`/`expires_at` (TTL черновика факта).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        raise NotImplementedError
