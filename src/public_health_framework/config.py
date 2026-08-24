"""Declarative PHFrame project configuration."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
import os
import re
from typing import Any

import yaml


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
FIELD_TYPES = {
    "string", "integer", "number", "boolean", "date", "datetime", "location",
    "identifier", "disease_code", "age", "sex", "case_classification",
    "epi_week", "reporting_period", "organisation_unit", "facility",
}
INDICATOR_OPERATIONS = {"count", "sum", "average", "rate", "ratio", "percentage"}
DATA_QUALITY_CHECKS = {"required", "range", "allowed"}
THRESHOLD_OPERATORS = {"gt", "gte", "lt", "lte", "eq"}


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
        numeric = {field_name for field_name, schema in dataset.fields.items() if schema.type in {"integer", "number", "age"}}
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
        if check == "range" and datasets[dataset_name].fields[field_name].type not in {"integer", "number", "age"}:
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
class SavedFilterSchema:
    name: str
    label: str
    dataset: str
    values: dict[str, Any]

    @classmethod
    def from_dict(
        cls, name: str, value: dict[str, Any], datasets: dict[str, DatasetSchema]
    ) -> "SavedFilterSchema":
        _validate_identifier(name, "saved filter")
        dataset_name = str(value.get("dataset", ""))
        if dataset_name not in datasets:
            raise ValueError(f"Saved filter '{name}' references unknown dataset '{dataset_name}'.")
        values = dict(value.get("values", {}) or {})
        if not values:
            raise ValueError(f"Saved filter '{name}' must define values.")
        unknown = set(values) - set(datasets[dataset_name].fields)
        if unknown:
            raise ValueError(f"Saved filter '{name}' references unknown fields: {', '.join(sorted(unknown))}.")
        return cls(
            name=name, label=str(value.get("label", name.replace("_", " ").title())),
            dataset=dataset_name, values=values,
        )


@dataclass(frozen=True)
class DimensionSchema:
    name: str
    label: str
    dataset: str
    field: str
    saved_filter: str | None = None

    @classmethod
    def from_dict(
        cls, name: str, value: dict[str, Any], datasets: dict[str, DatasetSchema],
        saved_filters: dict[str, SavedFilterSchema],
    ) -> "DimensionSchema":
        _validate_identifier(name, "dimension")
        dataset_name = str(value.get("dataset", ""))
        if dataset_name not in datasets:
            raise ValueError(f"Dimension '{name}' references unknown dataset '{dataset_name}'.")
        field_name = str(value.get("field", ""))
        if field_name not in datasets[dataset_name].fields:
            raise ValueError(f"Dimension '{name}' references unknown field '{field_name}'.")
        saved_filter = value.get("filter")
        if saved_filter:
            if saved_filter not in saved_filters:
                raise ValueError(f"Dimension '{name}' references unknown saved filter '{saved_filter}'.")
            if saved_filters[saved_filter].dataset != dataset_name:
                raise ValueError(f"Dimension '{name}' and saved filter '{saved_filter}' use different datasets.")
        return cls(
            name=name, label=str(value.get("label", name.replace("_", " ").title())),
            dataset=dataset_name, field=field_name, saved_filter=saved_filter,
        )


@dataclass(frozen=True)
class ThresholdSchema:
    name: str
    label: str
    indicator: str
    operator: str
    value: float
    severity: str = "warning"
    message: str | None = None

    @classmethod
    def from_dict(
        cls, name: str, value: dict[str, Any], indicators: dict[str, IndicatorSchema]
    ) -> "ThresholdSchema":
        _validate_identifier(name, "threshold")
        indicator_name = str(value.get("indicator", ""))
        if indicator_name not in indicators:
            raise ValueError(f"Threshold '{name}' references unknown indicator '{indicator_name}'.")
        operator = str(value.get("operator", "gte")).lower()
        if operator not in THRESHOLD_OPERATORS:
            raise ValueError(f"Threshold '{name}' has unsupported operator '{operator}'.")
        if "value" not in value:
            raise ValueError(f"Threshold '{name}' must define value.")
        severity = str(value.get("severity", "warning")).lower()
        if severity not in {"info", "warning", "critical"}:
            raise ValueError(f"Threshold '{name}' severity must be info, warning, or critical.")
        return cls(
            name=name, label=str(value.get("label", name.replace("_", " ").title())),
            indicator=indicator_name, operator=operator, value=float(value["value"]),
            severity=severity, message=value.get("message"),
        )


@dataclass(frozen=True)
class OrganisationUnitSchema:
    code: str
    name: str
    level: str
    parent: str | None = None

    @classmethod
    def from_dict(cls, code: str, value: dict[str, Any]) -> "OrganisationUnitSchema":
        _validate_identifier(code, "organisation-unit code")
        name = str(value.get("name", "")).strip()
        if not name:
            raise ValueError(f"Organisation unit '{code}' must define name.")
        level = str(value.get("level", "")).strip()
        if not level:
            raise ValueError(f"Organisation unit '{code}' must define level.")
        parent = value.get("parent")
        return cls(code=code, name=name, level=level, parent=str(parent) if parent else None)


@dataclass(frozen=True)
class DashboardWidgetSchema:
    type: str
    title: str
    indicator: str | None = None
    dimension: str | None = None
    dataset: str | None = None
    date_field: str | None = None
    value_field: str | None = None

    @classmethod
    def from_dict(
        cls, value: dict[str, Any], datasets: dict[str, DatasetSchema],
        indicators: dict[str, IndicatorSchema], dimensions: dict[str, DimensionSchema],
    ) -> "DashboardWidgetSchema":
        widget_type = str(value.get("type", ""))
        if widget_type not in {"kpi", "chart", "map", "epi_curve"}:
            raise ValueError(f"Unsupported dashboard widget type '{widget_type}'.")
        widget = cls(
            type=widget_type, title=str(value.get("title", widget_type.replace("_", " ").title())),
            indicator=value.get("indicator"), dimension=value.get("dimension"),
            dataset=value.get("dataset"), date_field=value.get("date_field"),
            value_field=value.get("value_field"),
        )
        if widget_type == "kpi" and widget.indicator not in indicators:
            raise ValueError(f"Dashboard KPI references unknown indicator '{widget.indicator}'.")
        if widget_type in {"chart", "map"} and widget.dimension not in dimensions:
            raise ValueError(f"Dashboard {widget_type} references unknown dimension '{widget.dimension}'.")
        if widget_type == "epi_curve":
            if widget.dataset not in datasets:
                raise ValueError(f"Dashboard epidemiological curve references unknown dataset '{widget.dataset}'.")
            fields = datasets[widget.dataset].fields
            if widget.date_field not in fields or fields[widget.date_field].type not in {"date", "datetime"}:
                raise ValueError("Dashboard epidemiological curve requires a date or datetime date_field.")
            if widget.value_field and (
                widget.value_field not in fields or fields[widget.value_field].type not in {"integer", "number"}
            ):
                raise ValueError("Dashboard epidemiological curve value_field must be numeric.")
        return widget


@dataclass(frozen=True)
class DashboardSchema:
    name: str
    label: str
    widgets: tuple[DashboardWidgetSchema, ...]


@dataclass(frozen=True)
class UIConfig:
    theme: str = "light"
    locale: str = "en"
    translations: dict[str, str] = dataclass_field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "UIConfig":
        theme = str(value.get("theme", "light"))
        if theme not in {"light", "dark", "high-contrast"}:
            raise ValueError("ui.theme must be light, dark, or high-contrast.")
        locale = str(value.get("locale", "en")).strip()
        if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", locale):
            raise ValueError("ui.locale must use a language code such as en or en-US.")
        translations = value.get("translations", {}) or {}
        if not isinstance(translations, dict):
            raise ValueError("ui.translations must be an object.")
        return cls(theme=theme, locale=locale, translations={str(key): str(item) for key, item in translations.items()})


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    database: str = "sqlite:///data/phframe.db"
    datasets: dict[str, DatasetSchema] = dataclass_field(default_factory=dict)
    indicators: dict[str, IndicatorSchema] = dataclass_field(default_factory=dict)
    data_quality_rules: dict[str, DataQualityRuleSchema] = dataclass_field(default_factory=dict)
    saved_filters: dict[str, SavedFilterSchema] = dataclass_field(default_factory=dict)
    dimensions: dict[str, DimensionSchema] = dataclass_field(default_factory=dict)
    thresholds: dict[str, ThresholdSchema] = dataclass_field(default_factory=dict)
    organisation_units: dict[str, OrganisationUnitSchema] = dataclass_field(default_factory=dict)
    dashboards: dict[str, DashboardSchema] = dataclass_field(default_factory=dict)
    ui: UIConfig = dataclass_field(default_factory=UIConfig)
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
        raw_filters = raw.get("filters", {})
        if not isinstance(raw_filters, dict):
            raise ValueError("Configuration 'filters' must be an object.")
        saved_filters = {
            name: SavedFilterSchema.from_dict(name, value or {}, datasets)
            for name, value in raw_filters.items()
        }
        raw_dimensions = raw.get("dimensions", {})
        if not isinstance(raw_dimensions, dict):
            raise ValueError("Configuration 'dimensions' must be an object.")
        dimensions = {
            name: DimensionSchema.from_dict(name, value or {}, datasets, saved_filters)
            for name, value in raw_dimensions.items()
        }
        raw_thresholds = raw.get("thresholds", {})
        if not isinstance(raw_thresholds, dict):
            raise ValueError("Configuration 'thresholds' must be an object.")
        thresholds = {
            name: ThresholdSchema.from_dict(name, value or {}, indicators)
            for name, value in raw_thresholds.items()
        }
        raw_units = raw.get("organisation_units", {})
        if not isinstance(raw_units, dict):
            raise ValueError("Configuration 'organisation_units' must be an object.")
        organisation_units = {
            code: OrganisationUnitSchema.from_dict(code, value or {})
            for code, value in raw_units.items()
        }
        _validate_organisation_units(organisation_units)
        raw_dashboards = raw.get("dashboards", {})
        if not isinstance(raw_dashboards, dict):
            raise ValueError("Configuration 'dashboards' must be an object.")
        dashboards = {}
        for dashboard_name, dashboard_value in raw_dashboards.items():
            _validate_identifier(dashboard_name, "dashboard")
            dashboard_value = dashboard_value or {}
            raw_widgets = dashboard_value.get("widgets", [])
            if not isinstance(raw_widgets, list):
                raise ValueError(f"Dashboard '{dashboard_name}' widgets must be a list.")
            dashboards[dashboard_name] = DashboardSchema(
                name=dashboard_name,
                label=str(dashboard_value.get("label", dashboard_name.replace("_", " ").title())),
                widgets=tuple(
                    DashboardWidgetSchema.from_dict(item or {}, datasets, indicators, dimensions)
                    for item in raw_widgets
                ),
            )
        raw_ui = raw.get("ui", {}) or {}
        if not isinstance(raw_ui, dict):
            raise ValueError("Configuration 'ui' must be an object.")
        ui = UIConfig.from_dict(raw_ui)
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
            saved_filters=saved_filters,
            dimensions=dimensions,
            thresholds=thresholds,
            organisation_units=organisation_units,
            dashboards=dashboards,
            ui=ui,
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


def _validate_organisation_units(units: dict[str, OrganisationUnitSchema]) -> None:
    for unit in units.values():
        if unit.parent and unit.parent not in units:
            raise ValueError(f"Organisation unit '{unit.code}' references unknown parent '{unit.parent}'.")
        seen = {unit.code}
        parent = unit.parent
        while parent:
            if parent in seen:
                raise ValueError(f"Organisation-unit hierarchy contains a cycle at '{parent}'.")
            seen.add(parent)
            parent = units[parent].parent
