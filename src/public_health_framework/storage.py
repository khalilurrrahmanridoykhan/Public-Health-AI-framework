"""SQLite persistence and validation for declarative datasets."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import json
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
        self.migrate()

    def migrate(self, check_only: bool = False) -> list[str]:
        """Create metadata/tables and apply safe additive schema changes."""
        actions: list[str] = []
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS _phframe_schema (
                    dataset TEXT PRIMARY KEY, schema_json TEXT NOT NULL, updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS _phframe_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                    total_rows INTEGER NOT NULL, imported_rows INTEGER NOT NULL,
                    error_rows INTEGER NOT NULL, errors_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            for dataset in self.config.datasets.values():
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (dataset.name,)
                ).fetchone()
                if not exists:
                    actions.append(f"create dataset {dataset.name}")
                    if not check_only:
                        connection.execute(self._create_table_sql(dataset))
                else:
                    current = {
                        row["name"]: row for row in connection.execute(f'PRAGMA table_info("{dataset.name}")').fetchall()
                    }
                    configured = set(dataset.fields)
                    managed = set(current) - {"id", "created_at", "updated_at"}
                    removed = managed - configured
                    if removed:
                        raise ValueError(
                            f"Dataset '{dataset.name}' removes fields ({', '.join(sorted(removed))}). "
                            "Destructive migrations are not automatic."
                        )
                    for name, schema in dataset.fields.items():
                        if name not in current:
                            if schema.required:
                                raise ValueError(
                                    f"Cannot add required field '{dataset.name}.{name}' automatically. "
                                    "Add it as optional, populate it, then make it required."
                                )
                            actions.append(f"add field {dataset.name}.{name}")
                            if not check_only:
                                connection.execute(f'ALTER TABLE "{dataset.name}" ADD COLUMN "{name}" {SQL_TYPES[schema.type]}')
                        else:
                            actual = str(current[name]["type"]).upper()
                            expected = SQL_TYPES[schema.type]
                            if actual != expected:
                                raise ValueError(
                                    f"Field '{dataset.name}.{name}' is {actual} in the database but {expected} in configuration."
                                )
                            actual_required = bool(current[name]["notnull"])
                            if actual_required != schema.required:
                                raise ValueError(
                                    f"Field '{dataset.name}.{name}' changes its required constraint. "
                                    "Constraint-changing migrations are not automatic."
                                )
                signature = self._schema_json(dataset)
                stored = connection.execute(
                    "SELECT schema_json FROM _phframe_schema WHERE dataset = ?", (dataset.name,)
                ).fetchone()
                if stored and stored["schema_json"] != signature and not actions:
                    actions.append(f"update metadata {dataset.name}")
                if not check_only:
                    connection.execute(
                        """INSERT INTO _phframe_schema(dataset, schema_json, updated_at) VALUES (?, ?, ?)
                        ON CONFLICT(dataset) DO UPDATE SET schema_json=excluded.schema_json, updated_at=excluded.updated_at""",
                        (dataset.name, signature, datetime.now().astimezone().isoformat()),
                    )
        return actions

    @staticmethod
    def _create_table_sql(dataset: DatasetSchema) -> str:
        columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        for name, schema in dataset.fields.items():
            required = " NOT NULL" if schema.required else ""
            columns.append(f'"{name}" {SQL_TYPES[schema.type]}{required}')
        columns.extend(["created_at TEXT NOT NULL", "updated_at TEXT NOT NULL"])
        return f'CREATE TABLE "{dataset.name}" ({", ".join(columns)})'

    @staticmethod
    def _schema_json(dataset: DatasetSchema) -> str:
        return json.dumps(
            {name: {"type": value.type, "required": value.required} for name, value in dataset.fields.items()},
            sort_keys=True,
        )

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

    def bulk_create(self, dataset: DatasetSchema, payloads: list[dict[str, Any]]) -> int:
        """Validate first, then insert all records in one transaction."""
        validated = [validate_payload(dataset, payload, partial=False) for payload in payloads]
        if not validated:
            return 0
        now = datetime.now().astimezone().isoformat()
        field_names = list(dataset.fields)
        names = [*field_names, "created_at", "updated_at"]
        quoted = ", ".join(f'"{name}"' for name in names)
        placeholders = ", ".join("?" for _ in names)
        rows = [tuple(values.get(name) for name in field_names) + (now, now) for values in validated]
        with self.connect() as connection:
            connection.executemany(
                f'INSERT INTO "{dataset.name}" ({quoted}) VALUES ({placeholders})', rows
            )
        return len(rows)

    def record_import(
        self,
        dataset: str,
        source: str,
        status: str,
        total_rows: int,
        imported_rows: int,
        errors: list[dict[str, Any]],
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO _phframe_imports
                (dataset, source, status, total_rows, imported_rows, error_rows, errors_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    dataset, source, status, total_rows, imported_rows, len(errors),
                    json.dumps(errors), datetime.now().astimezone().isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def import_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM _phframe_imports ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["errors"] = json.loads(item.pop("errors_json"))
            result.append(item)
        return result


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
