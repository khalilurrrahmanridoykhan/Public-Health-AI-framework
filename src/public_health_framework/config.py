"""Declarative PHFrame project configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
FIELD_TYPES = {"string", "integer", "number", "boolean", "date", "datetime", "location"}


@dataclass(frozen=True)
class FieldSchema:
    type: str = "string"
    required: bool = False
    protected: bool = False
    label: str | None = None

    @classmethod
    def from_value(cls, value: str | dict[str, Any]) -> "FieldSchema":
        if isinstance(value, str):
            result = cls(type=value)
        elif isinstance(value, dict):
            result = cls(
                type=str(value.get("type", "string")),
                required=bool(value.get("required", False)),
                protected=bool(value.get("protected", False)),
                label=value.get("label"),
            )
        else:
            raise ValueError("A field definition must be a type name or an object.")
        if result.type not in FIELD_TYPES:
            raise ValueError(f"Unsupported field type '{result.type}'.")
        return result


@dataclass(frozen=True)
class DatasetSchema:
    name: str
    label: str
    fields: dict[str, FieldSchema]

    @classmethod
    def from_dict(cls, name: str, value: dict[str, Any]) -> "DatasetSchema":
        _validate_identifier(name, "dataset")
        raw_fields = value.get("fields")
        if not isinstance(raw_fields, dict) or not raw_fields:
            raise ValueError(f"Dataset '{name}' must define at least one field.")
        fields: dict[str, FieldSchema] = {}
        for field_name, definition in raw_fields.items():
            _validate_identifier(field_name, "field")
            fields[field_name] = FieldSchema.from_value(definition)
        return cls(name=name, label=str(value.get("label", name.replace("_", " ").title())), fields=fields)


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    database: str = "sqlite:///data/phframe.db"
    datasets: dict[str, DatasetSchema] = field(default_factory=dict)
    plugins: tuple[str, ...] = ()
    root: Path = Path(".")

    @classmethod
    def load(cls, source: str | Path = "phframe.yaml") -> "ProjectConfig":
        path = Path(source).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PHFrame project configuration not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        project = raw.get("project", {})
        name = project.get("name")
        if not name:
            raise ValueError("Configuration must define project.name.")
        raw_datasets = raw.get("datasets", {})
        if not isinstance(raw_datasets, dict):
            raise ValueError("Configuration 'datasets' must be an object.")
        datasets = {name: DatasetSchema.from_dict(name, value or {}) for name, value in raw_datasets.items()}
        plugins = tuple(str(item) for item in raw.get("plugins", []))
        return cls(
            name=str(name),
            database=str(project.get("database", "sqlite:///data/phframe.db")),
            datasets=datasets,
            plugins=plugins,
            root=path.parent,
        )

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database.startswith(prefix):
            raise ValueError("Phase 1 currently supports sqlite:/// database URLs.")
        path = Path(self.database[len(prefix) :])
        return path if path.is_absolute() else (self.root / path).resolve()


def _validate_identifier(value: str, kind: str) -> None:
    if not IDENTIFIER.fullmatch(str(value)):
        raise ValueError(f"Invalid {kind} name '{value}'. Use lowercase letters, numbers, and underscores.")

