from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Setting:
    key: str
    value: str

