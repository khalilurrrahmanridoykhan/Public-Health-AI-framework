"""SQLite persistence and validation for declarative datasets."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .config import DatasetSchema, FieldSchema, ProjectConfig


SQL_TYPES = {
    "string": "TEXT",
    "location": "TEXT",
    "integer": "INTEGER",
    "number": "REAL",
    "boolean": "INTEGER",
    "date": "TEXT",
    "datetime": "TEXT",
}


class Storage:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.path = config.database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            for dataset in self.config.datasets.values():
                columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
                for name, schema in dataset.fields.items():
                    required = " NOT NULL" if schema.required else ""
                    columns.append(f'"{name}" {SQL_TYPES[schema.type]}{required}')
                columns.extend(["created_at TEXT NOT NULL", "updated_at TEXT NOT NULL"])
                connection.execute(f'CREATE TABLE IF NOT EXISTS "{dataset.name}" ({", ".join(columns)})')

    def list(self, dataset: DatasetSchema, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)
        with self.connect() as connection:
            rows = connection.execute(
                f'SELECT * FROM "{dataset.name}" ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, dataset: DatasetSchema, record_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(f'SELECT * FROM "{dataset.name}" WHERE id = ?', (record_id,)).fetchone()
        return dict(row) if row else None

    def create(self, dataset: DatasetSchema, payload: dict[str, Any]) -> dict[str, Any]:
        values = validate_payload(dataset, payload, partial=False)
        now = datetime.now().astimezone().isoformat()
        values.update(created_at=now, updated_at=now)
        names = list(values)
        quoted = ", ".join(f'"{name}"' for name in names)
        placeholders = ", ".join("?" for _ in names)
        with self.connect() as connection:
            cursor = connection.execute(
                f'INSERT INTO "{dataset.name}" ({quoted}) VALUES ({placeholders})',
                tuple(values.values()),
            )
            record_id = int(cursor.lastrowid)
        return self.get(dataset, record_id) or {}

    def update(self, dataset: DatasetSchema, record_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.get(dataset, record_id) is None:
            return None
        values = validate_payload(dataset, payload, partial=True)
        if not values:
            return self.get(dataset, record_id)
        values["updated_at"] = datetime.now().astimezone().isoformat()
        assignments = ", ".join(f'"{name}" = ?' for name in values)
        with self.connect() as connection:
            connection.execute(
                f'UPDATE "{dataset.name}" SET {assignments} WHERE id = ?',
                (*values.values(), record_id),
            )
        return self.get(dataset, record_id)

    def delete(self, dataset: DatasetSchema, record_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(f'DELETE FROM "{dataset.name}" WHERE id = ?', (record_id,))
        return cursor.rowcount > 0


def validate_payload(dataset: DatasetSchema, payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    unknown = set(payload) - set(dataset.fields)
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
    if not partial:
        missing = [name for name, schema in dataset.fields.items() if schema.required and payload.get(name) is None]
        if missing:
            raise ValueError(f"Required fields: {', '.join(missing)}")
    return {name: _coerce(name, value, dataset.fields[name]) for name, value in payload.items()}


def _coerce(name: str, value: Any, schema: FieldSchema) -> Any:
    if value is None:
        if schema.required:
            raise ValueError(f"Field '{name}' cannot be null.")
        return None
    try:
        if schema.type == "integer":
            return int(value)
        if schema.type == "number":
            return float(value)
        if schema.type == "boolean":
            if isinstance(value, str):
                normalized = value.lower()
                if normalized not in {"true", "false", "1", "0"}:
                    raise ValueError
                return int(normalized in {"true", "1"})
            return int(bool(value))
        if schema.type == "date":
            return date.fromisoformat(str(value)).isoformat()
        if schema.type == "datetime":
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
        return str(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Field '{name}' must be a valid {schema.type}.") from error

