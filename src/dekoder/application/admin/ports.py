"""
AdminAuthPort — не входит в 13 портов docs/versions/05, §7, но нужен:
единственная admin-учётка, перенесён из v1 без изменений.
"""

from __future__ import annotations

from typing import Protocol


class AdminAuthPort(Protocol):
    def authenticate(self, login: str, password: str) -> str: ...

    def validate_session(self, session_token: str) -> bool: ...
