from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Category:
    id: str | None
    name: str
    type: str
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1
