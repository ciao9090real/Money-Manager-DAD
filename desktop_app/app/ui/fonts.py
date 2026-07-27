from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase


_loaded = False


def _font_directory() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root) / "app" / "assets" / "fonts"
    return Path(__file__).resolve().parents[1] / "assets" / "fonts"


def load_app_fonts() -> None:
    """Register the bundled UI fonts once for source and packaged builds."""

    global _loaded
    if _loaded:
        return
    for filename in ("InterVariable.ttf", "SpaceGrotesk-Variable.ttf"):
        path = _font_directory() / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    _loaded = True
