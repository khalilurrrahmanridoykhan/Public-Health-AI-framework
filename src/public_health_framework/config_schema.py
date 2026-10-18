"""Versioned reference schema for ``phframe.yaml``.

The schema is a JSON Schema (draft 2020-12) document describing every key a
project configuration may contain. ``ProjectConfig.load`` validates each file
against it before building the project: a file that declares ``version: 1`` must
match exactly, while a file without ``version`` (a 0.9 preview project) is still
loaded and its findings are reported as warnings. Checks that need more than one
section, such as an indicator naming an existing dataset, stay in
``public_health_framework.config``.

``docs/phframe.schema.json`` and ``docs/configuration.md`` are generated from
this module. Regenerate both after an intentional change with::

    python -m public_health_framework.config_schema --write docs
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .config import DATA_QUALITY_CHECKS, FIELD_TYPES, INDICATOR_OPERATIONS, THRESHOLD_OPERATORS

CONFIG_VERSION = 1
SUPPORTED_VERSIONS = (CONFIG_VERSION,)
SCHEMA_ID = "https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/docs/phframe.schema.json"
IDENTIFIER_PATTERN = "^[a-z][a-z0-9_]*$"

WIDGET_TYPES = ["kpi", "chart", "map", "epi_curve"]
CONNECTOR_TYPES = ["api", "dhis2", "kobo", "odk"]

# Environment variables that override configuration values at load time.
ENVIRONMENT_OVERRIDES = [
    ("PHFRAME_CONFIG", "—", "Path of the configuration file loaded by `public_health_framework.runtime:app` (ASGI servers such as uvicorn). Default `phframe.yaml`."),
    ("PHFRAME_DATABASE_URL", "`project.database`", "Replaces the database URL."),
    ("PHFRAME_ENV", "`project.environment`", "Replaces the environment."),
    ("PHFRAME_HOST", "`server.host`", "Replaces the bind address."),
    ("PHFRAME_PORT", "`server.port`", "Replaces the port."),
]

# Sections in reference order, with the anchor used for each in the Markdown guide.
SECTIONS = [
    "version", "project", "server", "datasets", "indicators", "data_quality", "filters", "dimensions",
    "thresholds", "organisation_units", "dashboards", "ui", "connectors", "plugins",
]


# ---------------------------------------------------------------- schema helpers


def string(description: str, **extra: Any) -> dict[str, Any]:
    return {"type": "string", "description": description, **extra}


def obj(description: str, properties: dict[str, Any], required: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "description": description, "properties": properties}
    if required:
        schema["required"] = list(required)
    schema["additionalProperties"] = False
    schema.update(extra)
    return schema


def named(description: str, item: str, *, nullable: bool = False) -> dict[str, Any]:
    """An object whose keys are identifiers and whose values all use one definition."""
    return {
        "type": ["object", "null"] if nullable else "object",
        "description": description,
        "propertyNames": {"pattern": IDENTIFIER_PATTERN},
        "additionalProperties": {"$ref": f"#/$defs/{item}"},
    }


def label(kind: str) -> dict[str, Any]:
    return string(f"Display name. Defaults to the {kind} name in title case.")


def reference(kind: str, section: str) -> dict[str, Any]:
    article = "an" if kind[0] in "aeiou" else "a"
    return string(f"Name of {article} {kind} defined in `{section}`.")


def when(prop: str, value: Any, then: dict[str, Any]) -> dict[str, Any]:
    condition = {"enum": value} if isinstance(value, list) else {"const": value}
    return {"if": {"properties": {prop: condition}, "required": [prop]}, "then": then}


SCALAR = {"type": ["string", "number", "integer", "boolean"]}


def build_schema() -> dict[str, Any]:
    field_types = sorted(FIELD_TYPES)
    definitions = {
        "Field": {
            "description": "A dataset field: either a field type name, or an object with the type and options.",
            "oneOf": [
                {"type": "string", "enum": field_types, "description": "Shorthand for `{type: <name>}`."},
                obj("An object with the keys below.", {
                    "type": string("Field type. Determines storage and validation.", enum=field_types, default="string"),
                    "required": {"type": "boolean", "description": "Records must provide a value.", "default": False},
                    "protected": {"type": "boolean", "description": "Treated as sensitive: excluded from AI evidence and flagged by publication review.", "default": False},
                    "label": string("Display name. Defaults to the field name in title case."),
                }),
            ],
        },
        "Dataset": obj("A dataset stored as a database table with generated record endpoints.", {
            "label": label("dataset"),
            "fields": {
                "type": "object",
                "description": "Fields keyed by name. At least one is required.",
                "minProperties": 1,
                "propertyNames": {"pattern": IDENTIFIER_PATTERN},
                "additionalProperties": {"$ref": "#/$defs/Field"},
            },
        }, required=("fields",)),
        "Indicator": obj("A declarative indicator calculated over one dataset.", {
            "label": label("indicator"),
            "dataset": reference("dataset", "datasets"),
            "operation": string("Calculation to perform.", enum=sorted(INDICATOR_OPERATIONS), default="count"),
            "field": string("Numeric field to sum or average. Required for `sum` and `average`."),
            "numerator": string("Numeric numerator field. Required for `rate`, `ratio`, and `percentage`."),
            "denominator": string("Numeric denominator field. Required for `rate`, `ratio`, and `percentage`."),
            "multiplier": {"type": "number", "description": "Scale applied to the result. Defaults to 100 for `percentage` and 1 otherwise."},
            "date_field": string("Date or datetime field used for reporting periods."),
            "filters": {"type": ["object", "null"], "description": "Field values every counted record must match.", "default": {}},
        }, required=("dataset",), allOf=[
            when("operation", ["sum", "average"], {"required": ["field"]}),
            when("operation", ["rate", "ratio", "percentage"], {"required": ["numerator", "denominator"]}),
        ]),
        "DataQualityRule": obj("A data-quality rule evaluated over one field.", {
            "label": label("rule"),
            "dataset": reference("dataset", "datasets"),
            "field": string("Field the rule checks."),
            "check": string("`required` flags missing values, `range` flags numbers outside min/max, `allowed` flags values outside a list.",
                            enum=sorted(DATA_QUALITY_CHECKS), default="required"),
            "min": {"type": "number", "description": "Lowest accepted value for a `range` check."},
            "max": {"type": "number", "description": "Highest accepted value for a `range` check."},
            "values": {"type": "array", "description": "Accepted values for an `allowed` check.", "items": SCALAR, "minItems": 1},
        }, required=("dataset", "field"), allOf=[
            when("check", "range", {"anyOf": [{"required": ["min"]}, {"required": ["max"]}]}),
            when("check", "allowed", {"required": ["values"]}),
        ]),
        "SavedFilter": obj("A reusable set of field values for indicator and dimension queries.", {
            "label": label("filter"),
            "dataset": reference("dataset", "datasets"),
            "values": {"type": "object", "description": "Field values to match, keyed by field name.", "minProperties": 1},
        }, required=("dataset", "values")),
        "Dimension": obj("A grouped count of records by one field.", {
            "label": label("dimension"),
            "dataset": reference("dataset", "datasets"),
            "field": string("Field to group by."),
            "filter": string("Name of a saved filter defined in `filters` for the same dataset."),
        }, required=("dataset", "field")),
        "Threshold": obj("A surveillance alert evaluated against an indicator.", {
            "label": label("threshold"),
            "indicator": reference("indicator", "indicators"),
            "operator": string("Comparison between the indicator value and `value`.", enum=sorted(THRESHOLD_OPERATORS), default="gte"),
            "value": {"type": "number", "description": "Alert level."},
            "severity": string("Alert severity.", enum=["info", "warning", "critical"], default="warning"),
            "message": string("Message shown when the threshold is met."),
        }, required=("indicator", "value")),
        "OrganisationUnit": obj("A node in the organisation-unit hierarchy, keyed by its code.", {
            "name": string("Display name.", minLength=1),
            "level": string("Hierarchy level, such as country, district, or facility.", minLength=1),
            "parent": string("Code of the parent unit. The hierarchy may not contain cycles."),
        }, required=("name", "level")),
        "Widget": obj("A dashboard widget.", {
            "type": string("`kpi` shows an indicator, `chart` and `map` show a dimension, `epi_curve` plots records over time.", enum=WIDGET_TYPES),
            "title": string("Widget heading. Defaults to the widget type in title case."),
            "indicator": reference("indicator", "indicators") | {"description": "Indicator shown by a `kpi` widget."},
            "dimension": reference("dimension", "dimensions") | {"description": "Dimension shown by a `chart` or `map` widget."},
            "dataset": reference("dataset", "datasets") | {"description": "Dataset plotted by an `epi_curve` widget."},
            "date_field": string("Date or datetime field on the x-axis of an `epi_curve` widget."),
            "value_field": string("Numeric field summed per period by an `epi_curve` widget. Records are counted when omitted."),
        }, required=("type",), allOf=[
            when("type", "kpi", {"required": ["indicator"]}),
            when("type", ["chart", "map"], {"required": ["dimension"]}),
            when("type", "epi_curve", {"required": ["dataset", "date_field"]}),
        ]),
        "Dashboard": obj("A configured dashboard.", {
            "label": label("dashboard"),
            "widgets": {"type": "array", "description": "Widgets in display order.", "items": {"$ref": "#/$defs/Widget"}, "default": []},
        }),
        "Connector": obj("A scheduled pull from an external data source into a dataset.", {
            "type": string("Source system.", enum=CONNECTOR_TYPES),
            "dataset": reference("dataset", "datasets") | {"description": "Dataset that receives the records."},
            "base_url": string("Server address. Must start with `http://` or `https://`.", pattern="^https?://"),
            "resource": string("Resource path, form id, or DHIS2 data set id on the server.", minLength=1),
            "records_path": string("Dot-separated path to the record list when the response nests it."),
            "mapping": {
                "type": "object", "description": "Source field names mapped to dataset field names. At least one is required.",
                "minProperties": 1, "additionalProperties": {"type": "string"},
            },
            "auth": obj("Names of environment variables that hold credentials. Secrets never go in the file.", {
                "token_env": string("Variable holding an API token."),
                "username_env": string("Variable holding a user name for basic authentication."),
                "password_env": string("Variable holding a password for basic authentication."),
            }, type=["object", "null"]),
            "parameters": {"type": ["object", "null"], "description": "Extra query parameters sent with each request.", "additionalProperties": SCALAR},
            "timeout": {"type": "integer", "description": "Request timeout in seconds.", "minimum": 1, "maximum": 300, "default": 30},
            "schedule_minutes": {"type": ["integer", "null"], "description": "Minutes between scheduled runs by `phframe worker`. Manual only when omitted.", "minimum": 1},
        }, required=("type", "dataset", "base_url", "resource", "mapping")),
    }
    properties = {
        "version": {"type": "integer", "description": "Configuration schema version. Files without it are read as 0.9 preview projects.",
                    "enum": list(SUPPORTED_VERSIONS)},
        "project": obj("Project identity and storage.", {
            "name": string("Project name shown in the application header.", minLength=1),
            "database": string("SQLAlchemy database URL. Relative SQLite paths resolve against the configuration file. "
                               "`${NAME}` is replaced by the environment variable `NAME`.", default="sqlite:///data/phframe.db"),
            "environment": string("Deployment environment. `production` turns on the production readiness checks and disallows `phframe serve --reload`.",
                                  enum=["development", "test", "production"], default="development"),
        }, required=("name",)),
        "server": obj("Address that `phframe serve` binds to.", {
            "host": string("Address to bind.", default="127.0.0.1"),
            "port": {"type": "integer", "description": "Port to bind.", "minimum": 1, "maximum": 65535, "default": 8000},
        }, type=["object", "null"]),
        "datasets": named("Datasets keyed by name.", "Dataset"),
        "indicators": named("Indicators keyed by name.", "Indicator"),
        "data_quality": named("Data-quality rules keyed by name.", "DataQualityRule"),
        "filters": named("Saved filters keyed by name.", "SavedFilter"),
        "dimensions": named("Dimensions keyed by name.", "Dimension"),
        "thresholds": named("Surveillance thresholds keyed by name.", "Threshold"),
        "organisation_units": named("Organisation units keyed by code.", "OrganisationUnit"),
        "dashboards": named("Dashboards keyed by name.", "Dashboard"),
        "ui": obj("Browser application appearance.", {
            "theme": string("Default colour theme.", enum=["light", "dark", "high-contrast"], default="light"),
            "locale": string("Interface language, such as `en` or `en-US`.", pattern="^[a-z]{2}(-[A-Z]{2})?$", default="en"),
            "translations": {"type": ["object", "null"], "description": "Interface strings keyed by message id.",
                             "additionalProperties": SCALAR, "default": {}},
        }, type=["object", "null"]),
        "connectors": named("Connectors keyed by name.", "Connector", nullable=True),
        "plugins": {"type": "array", "description": "Plugins loaded at start-up, in order, written as `module` or `module:attribute`. Each must provide `setup(app, config)`.",
                    "items": {"type": "string"}, "default": []},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "PHFrame project configuration",
        "description": f"Schema for phframe.yaml, configuration version {CONFIG_VERSION}.",
        "type": "object",
        "properties": properties,
        "required": ["version", "project"],
        "additionalProperties": False,
        "$defs": definitions,
    }


# ---------------------------------------------------------------- validation


@dataclass(frozen=True)
class ConfigIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path or '(root)'}: {self.message}"


_TYPES = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


def _join(path: str, key: Any) -> str:
    return f"{path}[{key}]" if isinstance(key, int) else (f"{path}.{key}" if path else str(key))


class _Validator:
    """Checks the subset of JSON Schema that ``build_schema`` uses."""

    def __init__(self, schema: dict[str, Any]):
        self.root = schema

    def resolve(self, schema: dict[str, Any]) -> dict[str, Any]:
        while "$ref" in schema:
            schema = self.root["$defs"][schema["$ref"].rsplit("/", 1)[1]]
        return schema

    def check(self, value: Any, schema: dict[str, Any], path: str) -> list[ConfigIssue]:
        schema = self.resolve(schema)
        issues: list[ConfigIssue] = []
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_TYPES[name](value) for name in types):
                return [ConfigIssue(path, f"expected {' or '.join(types)}, got {_describe(value)}")]
        if "const" in schema and value != schema["const"]:
            issues.append(ConfigIssue(path, f"must be {schema['const']!r}"))
        if "enum" in schema and value not in schema["enum"]:
            issues.append(ConfigIssue(path, f"must be one of {', '.join(str(item) for item in schema['enum'])}; got {value!r}"))
        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                issues.append(ConfigIssue(path, "must not be empty"))
            if "pattern" in schema and not re.search(schema["pattern"], value):
                issues.append(ConfigIssue(path, f"{value!r} does not match {schema['pattern']}"))
        if _TYPES["number"](value):
            if "minimum" in schema and value < schema["minimum"]:
                issues.append(ConfigIssue(path, f"must be at least {schema['minimum']}"))
            if "maximum" in schema and value > schema["maximum"]:
                issues.append(ConfigIssue(path, f"must be at most {schema['maximum']}"))
        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                issues.append(ConfigIssue(path, f"must contain at least {schema['minItems']} item(s)"))
            if "items" in schema:
                for index, item in enumerate(value):
                    issues += self.check(item, schema["items"], _join(path, index))
        if isinstance(value, dict):
            issues += self.check_object(value, schema, path)
        if "oneOf" in schema:
            matches = [self.check(value, option, path) for option in schema["oneOf"]]
            if all(matches):
                # Report against the option whose type fits the value, so the message names the real mistake.
                fitting = [found for found, option in zip(matches, schema["oneOf"]) if self.type_fits(value, option)]
                issues += min(fitting or matches, key=len)
            elif sum(not found for found in matches) > 1:
                issues.append(ConfigIssue(path, "matches more than one allowed form"))
        if "anyOf" in schema:
            matches = [self.check(value, option, path) for option in schema["anyOf"]]
            if all(matches):
                issues += matches[0]
        for clause in schema.get("allOf", []):
            if "if" in clause:
                if not self.check(value, clause["if"], path):
                    issues += self.check(value, clause["then"], path)
            else:
                issues += self.check(value, clause, path)
        return issues

    def type_fits(self, value: Any, schema: dict[str, Any]) -> bool:
        types = self.resolve(schema).get("type")
        if types is None:
            return True
        return any(_TYPES[name](value) for name in (types if isinstance(types, list) else [types]))

    def check_object(self, value: dict[str, Any], schema: dict[str, Any], path: str) -> list[ConfigIssue]:
        issues: list[ConfigIssue] = []
        for key in schema.get("required", []):
            if key not in value:
                issues.append(ConfigIssue(path, f"missing required key '{key}'"))
        if len(value) < schema.get("minProperties", 0):
            issues.append(ConfigIssue(path, f"must define at least {schema['minProperties']} entry"))
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for key, item in value.items():
            child = _join(path, key)
            if names and not re.search(names["pattern"], str(key)):
                issues.append(ConfigIssue(child, "invalid name; use lowercase letters, numbers, and underscores, starting with a letter"))
                continue
            if key in properties:
                issues += self.check(item, properties[key], child)
            elif extra is False:
                issues.append(ConfigIssue(child, f"unknown key{_suggest(key, properties)}"))
            elif isinstance(extra, dict):
                issues += self.check(item, extra, child)
        return issues


def _describe(value: Any) -> str:
    if value is None:
        return "null"
    return {bool: "boolean", int: "integer", float: "number", str: "string", list: "array", dict: "object"}.get(type(value), type(value).__name__)


def _suggest(key: Any, properties: dict[str, Any]) -> str:
    from difflib import get_close_matches

    close = get_close_matches(str(key), list(properties), n=1)
    return f"; did you mean '{close[0]}'?" if close else ""


def validate_config(raw: Any, schema: dict[str, Any] | None = None) -> list[ConfigIssue]:
    """Return every place where ``raw`` differs from the configuration schema."""
    schema = schema or build_schema()
    return _Validator(schema).check(raw, schema, "")


def validate_section(section: str, name: str, value: Any) -> list[ConfigIssue]:
    """Validate one named entry, such as a connector posted through the HTTP API."""
    schema = build_schema()
    item = schema["properties"][section]["additionalProperties"]
    return _Validator(schema).check(value, item, f"{section}.{name}")


# ---------------------------------------------------------------- Markdown reference


def _type(schema: dict[str, Any], root: dict[str, Any]) -> str:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[1]
        return f"[{name}](#{name.lower()})"
    if "oneOf" in schema:
        return " or ".join(_type(option, root) for option in schema["oneOf"])
    types = schema.get("type", "any")
    types = [item for item in (types if isinstance(types, list) else [types]) if item != "null"]
    if types == ["object"] and isinstance(schema.get("additionalProperties"), dict) and "properties" not in schema:
        return f"map of {_type(schema['additionalProperties'], root)}"
    if types == ["array"] and "items" in schema:
        return f"list of {_type(schema['items'], root)}"
    if len(types) == 4 and "boolean" in types:
        return "scalar"
    return " or ".join(types)


def _constraints(schema: dict[str, Any]) -> str:
    notes = []
    if "enum" in schema and schema.get("type") != "integer":
        notes.append("One of " + ", ".join(f"`{item}`" for item in schema["enum"]) + ".")
    if "minimum" in schema and "maximum" in schema:
        notes.append(f"{schema['minimum']}–{schema['maximum']}.")
    elif "minimum" in schema:
        notes.append(f"At least {schema['minimum']}.")
    if "pattern" in schema:
        notes.append(f"Matches `{schema['pattern']}`.")
    return " ".join(notes)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _rows(schema: dict[str, Any], root: dict[str, Any], prefix: str = "", nested: bool = True) -> list[str]:
    required = set(schema.get("required", []))
    lines = []
    for key, item in schema.get("properties", {}).items():
        default = f"`{json.dumps(item['default'])}`" if "default" in item else ""
        description = " ".join(part for part in [item.get("description", ""), _constraints(item)] if part)
        lines.append(f"| `{prefix}{key}` | {_type(item, root)} | {'yes' if key in required else ''} | {default} | {_cell(description)} |")
        if nested:
            lines += _rows(item, root, f"{prefix}{key}.")
    return lines


def _table(schema: dict[str, Any], root: dict[str, Any], nested: bool = True) -> list[str]:
    return ["| Key | Type | Required | Default | Description |", "|---|---|---|---|---|"] + _rows(schema, root, nested=nested) + [""]


def _conditions(schema: dict[str, Any]) -> list[str]:
    lines = []
    for clause in schema.get("allOf", []):
        (prop, condition), = clause["if"]["properties"].items()
        values = condition.get("enum", [condition.get("const")])
        then = clause["then"]
        if "required" in then:
            needs = " and ".join(f"`{item}`" for item in then["required"])
        else:
            needs = " or ".join(f"`{option['required'][0]}`" for option in then["anyOf"])
        lines.append(f"- When `{prop}` is " + " or ".join(f"`{value}`" for value in values) + f", {needs} must be set.")
    return lines + [""] if lines else []


EXAMPLE = """version: 1

project:
  name: Malaria Surveillance
  database: ${DATABASE_URL}
  environment: production

datasets:
  case_reports:
    fields:
      case_id: {type: identifier, required: true, protected: true}
      report_date: {type: date, required: true}
      district: location
      cases: {type: integer, required: true}
      population: integer

indicators:
  incidence_per_1000:
    dataset: case_reports
    operation: rate
    numerator: cases
    denominator: population
    multiplier: 1000
    date_field: report_date

dashboards:
  main:
    widgets:
      - {type: kpi, indicator: incidence_per_1000}
      - {type: epi_curve, dataset: case_reports, date_field: report_date, value_field: cases}
"""


def build_markdown(schema: dict[str, Any] | None = None) -> str:
    schema = schema or build_schema()
    lines = [
        "# Configuration reference",
        "",
        "<!-- Generated by `python -m public_health_framework.config_schema --write docs`. Do not edit by hand. -->",
        "",
        f"Every PHFrame project is described by a `phframe.yaml` file. This page documents configuration version {CONFIG_VERSION}; "
        "the machine-readable JSON Schema is [`phframe.schema.json`](phframe.schema.json), which editors such as VS Code can use "
        "for completion by adding `# yaml-language-server: $schema=<url of phframe.schema.json>` to the top of the file.",
        "",
        "## Versioning and validation",
        "",
        f"- Declare `version: {CONFIG_VERSION}` at the top of the file. `phframe new` writes it for you.",
        f"- A file with `version: {CONFIG_VERSION}` must match the schema exactly: unknown keys, wrong types, and values outside "
        "the allowed set stop `phframe check`, `phframe serve`, and every other command with an error naming the key, such as "
        "`datasets.case_reports.fields.cases.requird: unknown key; did you mean 'required'?`.",
        "- A file without `version` is read as a 0.9 preview project. It loads as before, and `phframe check` prints each schema "
        f"finding as a warning so it can be fixed before adding `version: {CONFIG_VERSION}`.",
        "- Any other version is rejected, so a project written for a newer PHFrame is never misread.",
        "- A new configuration version is introduced only in a major release, with a documented migration.",
        "- After the schema check, PHFrame also checks references between sections: indicators, rules, filters, dimensions, "
        "widgets, and connectors must name datasets and fields that exist; measure fields must be numeric; `date_field` must be "
        "a date or datetime field; thresholds must name an indicator; and the organisation-unit hierarchy must not contain cycles.",
        "- Connectors created through `POST /api/connectors` are checked against the same schema before they are saved.",
        "",
        "## Example",
        "",
        "```yaml",
        EXAMPLE.rstrip(),
        "```",
        "",
        "## Environment variables",
        "",
        "| Variable | Overrides | Description |",
        "|---|---|---|",
    ]
    lines += [f"| `{name}` | {target} | {description} |" for name, target, description in ENVIRONMENT_OVERRIDES]
    lines += ["", "## Top-level keys", ""] + _table(schema, schema, nested=False)
    for section in SECTIONS:
        item = schema["properties"][section]
        if "properties" in item:
            lines += [f"## `{section}`", "", item["description"], ""] + _table(item, schema)
    lines += ["## Definitions", ""]
    for name, definition in schema["$defs"].items():
        lines += [f"### {name}", "", definition["description"], ""]
        if "oneOf" in definition:
            for option in definition["oneOf"]:
                lines.append(f"- {option['description']}" + (" One of " + ", ".join(f"`{item}`" for item in option["enum"]) + "." if "enum" in option else ""))
            lines.append("")
            definition = next(option for option in definition["oneOf"] if option.get("type") == "object")
        lines += _table(definition, schema) + _conditions(definition)
    return "\n".join(lines).rstrip() + "\n"


def write(directory: Path) -> None:
    schema = build_schema()
    (directory / "phframe.schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    (directory / "configuration.md").write_text(build_markdown(schema), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Print or write the phframe.yaml configuration reference.")
    parser.add_argument("--write", metavar="DIRECTORY", help="Write phframe.schema.json and configuration.md into this directory.")
    parser.add_argument("--markdown", action="store_true", help="Print the Markdown reference instead of the JSON Schema.")
    arguments = parser.parse_args()
    if arguments.write:
        write(Path(arguments.write))
    elif arguments.markdown:
        print(build_markdown(), end="")
    else:
        print(json.dumps(build_schema(), indent=2))


if __name__ == "__main__":
    main()
