from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "MoneyManagerDAD"


def app_data_dir() -> Path:
    override = os.environ.get("MONEY_MANAGER_DAD_DATA_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def backup_dir() -> Path:
    return app_data_dir() / "backups"


def export_dir() -> Path:
    return app_data_dir() / "exports"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def database_path() -> Path:
    return app_data_dir() / "money_manager.db"


def database_key_path() -> Path:
    return app_data_dir() / "database.key"


def ensure_app_dirs() -> None:
    for path in (app_data_dir(), backup_dir(), export_dir(), log_dir()):
        path.mkdir(parents=True, exist_ok=True)
