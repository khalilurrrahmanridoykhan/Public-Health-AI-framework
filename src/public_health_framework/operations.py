"""Backup, restore, retention, and operational diagnostics."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from .production import validate_production_environment


def backup(config: Any, destination: str | Path | None = None) -> Path:
    if not config.database_url.startswith("sqlite:"): raise ValueError("Built-in backup currently supports SQLite; use pg_dump for PostgreSQL.")
    target = Path(destination) if destination else config.root / "backups" / f"phframe-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(config.database_path); output = sqlite3.connect(target)
    try: source.backup(output)
    finally: output.close(); source.close()
    return target


def restore(config: Any, source: str | Path) -> Path:
    if not config.database_url.startswith("sqlite:"): raise ValueError("Built-in restore currently supports SQLite; use pg_restore for PostgreSQL.")
    source_path = Path(source)
    if not source_path.is_file(): raise ValueError(f"Backup not found: {source_path}")
    with sqlite3.connect(source_path) as connection: connection.execute("PRAGMA integrity_check").fetchone()
    config.database_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source_path, config.database_path); return config.database_path


def doctor(config: Any) -> dict[str, Any]:
    from .storage import Storage
    storage = Storage(config); storage.initialize()
    return {"status": "ok", "environment": config.environment, "database": config.database_url.split(":", 1)[0], "datasets": len(config.datasets), "issues": validate_production_environment(config)}
