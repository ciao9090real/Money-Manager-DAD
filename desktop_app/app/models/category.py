from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Category:
    id: int | None
    name: str
    type: str
    is_active: bool = True

