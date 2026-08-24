"""Declarative PHFrame project configuration."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
import os
import re
from typing import Any

import yaml


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
FIELD_TYPES = {"string", "integer", "number", "boolean", "date", "datetime", "location"}
INDICATOR_OPERATIONS = {"count", "sum", "average", "rate", "ratio", "percentage"}
DATA_QUALITY_CHECKS = {"required", "range", "allowed"}


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
class IndicatorSchema:
    name: str
    label: str
    dataset: str
    operation: str
    field: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    multiplier: float = 1.0
    date_field: str | None = None
    filters: dict[str, Any] = dataclass_field(default_factory=dict)

    @classmethod
    def from_dict(
        cls, name: str, value: dict[str, Any], datasets: dict[str, DatasetSchema]
    ) -> "IndicatorSchema":
        _validate_identifier(name, "indicator")
        dataset_name = str(value.get("dataset", ""))
        if dataset_name not in datasets:
            raise ValueError(f"Indicator '{name}' references unknown dataset '{dataset_name}'.")
        dataset = datasets[dataset_name]
        operation = str(value.get("operation", "count")).lower()
        if operation not in INDICATOR_OPERATIONS:
            raise ValueError(f"Indicator '{name}' has unsupported operation '{operation}'.")
        indicator = cls(
            name=name,
            label=str(value.get("label", name.replace("_", " ").title())),
            dataset=dataset_name,
            operation=operation,
            field=value.get("field"),
            numerator=value.get("numerator"),
            denominator=value.get("denominator"),
            multiplier=float(value.get("multiplier", 100 if operation == "percentage" else 1)),
            date_field=value.get("date_field"),
            filters=dict(value.get("filters", {}) or {}),
        )
        referenced = [indicator.date_field, *indicator.filters]
        if operation in {"sum", "average"}:
            if not indicator.field:
                raise ValueError(f"Indicator '{name}' must define field for {operation}.")
            referenced.append(indicator.field)
        if operation in {"rate", "ratio", "percentage"}:
            if not indicator.numerator or not indicator.denominator:
                raise ValueError(f"Indicator '{name}' must define numerator and denominator.")
            referenced.extend([indicator.numerator, indicator.denominator])
        unknown = [item for item in referenced if item and item not in dataset.fields]
        if unknown:
            raise ValueError(f"Indicator '{name}' references unknown fields: {', '.join(unknown)}.")
        numeric = {field_name for field_name, schema in dataset.fields.items() if schema.type in {"integer", "number"}}
        measures = [item for item in [indicator.field, indicator.numerator, indicator.denominator] if item]
        if any(item not in numeric for item in measures):
            raise ValueError(f"Indicator '{name}' measure fields must be integer or number fields.")
        if indicator.date_field and dataset.fields[indicator.date_field].type not in {"date", "datetime"}:
            raise ValueError(f"Indicator '{name}' date_field must be a date or datetime field.")
        return indicator


@dataclass(frozen=True)
class DataQualityRuleSchema:
    name: str
    label: str
    dataset: str
    field: str
    check: str
    minimum: float | None = None
    maximum: float | None = None
    values: tuple[Any, ...] = ()

    @classmethod
    def from_dict(
        cls, name: str, value: dict[str, Any], datasets: dict[str, DatasetSchema]
    ) -> "DataQualityRuleSchema":
        _validate_identifier(name, "data-quality rule")
        dataset_name = str(value.get("dataset", ""))
        if dataset_name not in datasets:
            raise ValueError(f"Data-quality rule '{name}' references unknown dataset '{dataset_name}'.")
        field_name = str(value.get("field", ""))
        if field_name not in datasets[dataset_name].fields:
            raise ValueError(f"Data-quality rule '{name}' references unknown field '{field_name}'.")
        check = str(value.get("check", "required")).lower()
        if check not in DATA_QUALITY_CHECKS:
            raise ValueError(f"Data-quality rule '{name}' has unsupported check '{check}'.")
        minimum = value.get("min")
        maximum = value.get("max")
        values = tuple(value.get("values", ()) or ())
        if check == "range" and minimum is None and maximum is None:
            raise ValueError(f"Data-quality rule '{name}' must define min or max.")
        if check == "range" and datasets[dataset_name].fields[field_name].type not in {"integer", "number"}:
            raise ValueError(f"Data-quality rule '{name}' requires a numeric field for range checks.")
        if check == "allowed" and not values:
            raise ValueError(f"Data-quality rule '{name}' must define values.")
        return cls(
            name=name, label=str(value.get("label", name.replace("_", " ").title())),
            dataset=dataset_name, field=field_name, check=check,
            minimum=float(minimum) if minimum is not None else None,
            maximum=float(maximum) if maximum is not None else None, values=values,
        )


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    database: str = "sqlite:///data/phframe.db"
    datasets: dict[str, DatasetSchema] = dataclass_field(default_factory=dict)
    indicators: dict[str, IndicatorSchema] = dataclass_field(default_factory=dict)
    data_quality_rules: dict[str, DataQualityRuleSchema] = dataclass_field(default_factory=dict)
    plugins: tuple[str, ...] = ()
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
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
        raw_indicators = raw.get("indicators", {})
        if not isinstance(raw_indicators, dict):
            raise ValueError("Configuration 'indicators' must be an object.")
        indicators = {
            name: IndicatorSchema.from_dict(name, value or {}, datasets)
            for name, value in raw_indicators.items()
        }
        raw_rules = raw.get("data_quality", {})
        if not isinstance(raw_rules, dict):
            raise ValueError("Configuration 'data_quality' must be an object.")
        data_quality_rules = {
            name: DataQualityRuleSchema.from_dict(name, value or {}, datasets)
            for name, value in raw_rules.items()
        }
        plugins = tuple(str(item) for item in raw.get("plugins", []))
        database = os.environ.get("PHFRAME_DATABASE_URL") or _expand_env(
            str(project.get("database", "sqlite:///data/phframe.db"))
        )
        environment = os.environ.get("PHFRAME_ENV", str(project.get("environment", "development"))).lower()
        if environment not in {"development", "test", "production"}:
            raise ValueError("project.environment must be development, test, or production.")
        server = raw.get("server", {}) or {}
        return cls(
            name=str(name),
            database=database,
            datasets=datasets,
            indicators=indicators,
            data_quality_rules=data_quality_rules,
            plugins=plugins,
            environment=environment,
            host=os.environ.get("PHFRAME_HOST", str(server.get("host", "127.0.0.1"))),
            port=int(os.environ.get("PHFRAME_PORT", server.get("port", 8000))),
            root=path.parent,
        )

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database.startswith(prefix):
            raise ValueError("database_path is only available for SQLite projects.")
        path = Path(self.database[len(prefix) :])
        return path if path.is_absolute() else (self.root / path).resolve()

    @property
    def database_url(self) -> str:
        if not self.database.startswith("sqlite:///"):
            return self.database
        return f"sqlite:///{self.database_path}"

    @property
    def database_display(self) -> str:
        if self.database.startswith("sqlite:///"):
            return str(self.database_path)
        scheme, separator, remainder = self.database.partition("://")
        if separator and "@" in remainder:
            return f"{scheme}://***@{remainder.rsplit('@', 1)[1]}"
        return self.database


def _expand_env(value: str) -> str:
    pattern = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ValueError(f"Required environment variable is not set: {name}")
        return os.environ[name]

    return pattern.sub(replace, value)


def _validate_identifier(value: str, kind: str) -> None:
    if not IDENTIFIER.fullmatch(str(value)):
        raise ValueError(f"Invalid {kind} name '{value}'. Use lowercase letters, numbers, and underscores.")
