from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.paths import ensure_app_dirs, log_dir


LOG_FILE_NAME = "money-manager.log"


def configure_logging() -> None:
    """Write bounded local diagnostics without recording financial data."""

    ensure_app_dirs()
    target = log_dir() / LOG_FILE_NAME
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler) and getattr(
            handler, "baseFilename", ""
        ) == str(target):
            return
    handler = RotatingFileHandler(
        target,
        maxBytes=512_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
