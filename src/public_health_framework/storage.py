"""Portable SQL persistence and validation for declarative datasets."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text,
    and_, create_engine, delete, func, inspect, insert, or_, select, update,
)
from sqlalchemy.schema import CreateColumn

from .config import DataQualityRuleSchema, DatasetSchema, DimensionSchema, FieldSchema, IndicatorSchema, ProjectConfig
from .periods import resolve_period


TYPE_FACTORIES = {
    "string": Text,
    "location": Text,
    "integer": Integer,
    "number": Float,
    "boolean": Boolean,
    "date": Date,
    "datetime": DateTime,
    "identifier": Text,
    "disease_code": Text,
    "age": Integer,
    "sex": Text,
    "case_classification": Text,
    "epi_week": Text,
    "reporting_period": Text,
    "organisation_unit": Text,
    "facility": Text,
}

TEXT_TYPES = {
    "string", "location", "identifier", "disease_code", "sex", "case_classification",
    "epi_week", "reporting_period", "organisation_unit", "facility",
}


class Storage:
    def __init__(self, config: ProjectConfig):
        self.config = config
        if config.database.startswith("sqlite:///"):
            config.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(config.database_url, future=True, pool_pre_ping=True)
        self.metadata = MetaData()
        self.schema_table = Table(
            "_phframe_schema", self.metadata,
            Column("dataset", String(255), primary_key=True),
            Column("schema_json", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.imports_table = Table(
            "_phframe_imports", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("dataset", String(255), nullable=False),
            Column("source", Text, nullable=False),
            Column("status", String(32), nullable=False),
            Column("total_rows", Integer, nullable=False),
            Column("imported_rows", Integer, nullable=False),
            Column("error_rows", Integer, nullable=False),
            Column("errors_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )

    def initialize(self) -> None:
        self.migrate()

    def _dataset_table(self, dataset: DatasetSchema) -> Table:
        existing = self.metadata.tables.get(dataset.name)
        if existing is not None:
            return existing
        columns = [Column("id", Integer, primary_key=True, autoincrement=True)]
        columns.extend(
            Column(name, TYPE_FACTORIES[schema.type](), nullable=not schema.required)
            for name, schema in dataset.fields.items()
        )
        columns.extend([
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        ])
        return Table(dataset.name, self.metadata, *columns)

    def migrate(self, check_only: bool = False) -> list[str]:
        """Create metadata/tables and apply safe additive schema changes."""
        self.metadata.create_all(self.engine, tables=[self.schema_table, self.imports_table])
        actions: list[str] = []
        inspector = inspect(self.engine)
        for dataset in self.config.datasets.values():
            table = self._dataset_table(dataset)
            dataset_actions: list[str] = []
            if not inspector.has_table(dataset.name):
                dataset_actions.append(f"create dataset {dataset.name}")
                if not check_only:
                    table.create(self.engine)
            else:
                current = {column["name"]: column for column in inspector.get_columns(dataset.name)}
                managed = set(current) - {"id", "created_at", "updated_at"}
                removed = managed - set(dataset.fields)
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
                        dataset_actions.append(f"add field {dataset.name}.{name}")
                        if not check_only:
                            definition = str(CreateColumn(table.c[name]).compile(dialect=self.engine.dialect))
                            with self.engine.begin() as connection:
                                connection.exec_driver_sql(f'ALTER TABLE "{dataset.name}" ADD COLUMN {definition}')
                    else:
                        actual_type = _type_key(current[name]["type"])
                        if not _compatible_type(schema.type, actual_type, self.engine.dialect.name):
                            raise ValueError(
                                f"Field '{dataset.name}.{name}' is {actual_type} in the database "
                                f"but {schema.type} in configuration."
                            )
                        actual_required = not bool(current[name]["nullable"])
                        if actual_required != schema.required:
                            raise ValueError(
                                f"Field '{dataset.name}.{name}' changes its required constraint. "
                                "Constraint-changing migrations are not automatic."
                            )
            actions.extend(dataset_actions)
            signature = self._schema_json(dataset)
            with self.engine.begin() as connection:
                stored = connection.execute(
                    select(self.schema_table.c.schema_json).where(self.schema_table.c.dataset == dataset.name)
                ).scalar_one_or_none()
                if stored and stored != signature and not dataset_actions:
                    actions.append(f"update metadata {dataset.name}")
                if not check_only:
                    connection.execute(delete(self.schema_table).where(self.schema_table.c.dataset == dataset.name))
                    connection.execute(insert(self.schema_table).values(
                        dataset=dataset.name, schema_json=signature, updated_at=_now()
                    ))
        return actions

    @staticmethod
    def _schema_json(dataset: DatasetSchema) -> str:
        return json.dumps(
            {name: {"type": value.type, "required": value.required} for name, value in dataset.fields.items()},
            sort_keys=True,
        )

    def list(self, dataset: DatasetSchema, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        table = self._dataset_table(dataset)
        statement = select(table).order_by(table.c.id.desc()).limit(max(1, min(limit, 1000))).offset(max(0, offset))
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_serialize(dict(row)) for row in rows]

    def get(self, dataset: DatasetSchema, record_id: int) -> dict[str, Any] | None:
        table = self._dataset_table(dataset)
        with self.engine.connect() as connection:
            row = connection.execute(select(table).where(table.c.id == record_id)).mappings().first()
        return _serialize(dict(row)) if row else None

    def create(self, dataset: DatasetSchema, payload: dict[str, Any]) -> dict[str, Any]:
        values = validate_payload(dataset, payload, partial=False)
        self._validate_organisation_units(dataset, values)
        now = _now()
        values.update(created_at=now, updated_at=now)
        table = self._dataset_table(dataset)
        with self.engine.begin() as connection:
            result = connection.execute(insert(table).values(**values))
            record_id = int(result.inserted_primary_key[0])
        return self.get(dataset, record_id) or {}

    def update(self, dataset: DatasetSchema, record_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        table = self._dataset_table(dataset)
        if self.get(dataset, record_id) is None:
            return None
        values = validate_payload(dataset, payload, partial=True)
        self._validate_organisation_units(dataset, values)
        if values:
            values["updated_at"] = _now()
            with self.engine.begin() as connection:
                connection.execute(update(table).where(table.c.id == record_id).values(**values))
        return self.get(dataset, record_id)

    def delete(self, dataset: DatasetSchema, record_id: int) -> bool:
        table = self._dataset_table(dataset)
        with self.engine.begin() as connection:
            result = connection.execute(delete(table).where(table.c.id == record_id))
        return bool(result.rowcount)

    def bulk_create(self, dataset: DatasetSchema, payloads: list[dict[str, Any]]) -> int:
        validated = [validate_payload(dataset, payload, partial=False) for payload in payloads]
        for values in validated:
            self._validate_organisation_units(dataset, values)
        if not validated:
            return 0
        now = _now()
        rows = [{**values, "created_at": now, "updated_at": now} for values in validated]
        with self.engine.begin() as connection:
            connection.execute(insert(self._dataset_table(dataset)), rows)
        return len(rows)

    def _validate_organisation_units(self, dataset: DatasetSchema, values: dict[str, Any]) -> None:
        if not self.config.organisation_units:
            return
        for name, schema in dataset.fields.items():
            value = values.get(name)
            if schema.type == "organisation_unit" and value is not None and value not in self.config.organisation_units:
                raise ValueError(f"Field '{name}' references unknown organisation unit '{value}'.")

    def record_import(
        self, dataset: str, source: str, status: str, total_rows: int,
        imported_rows: int, errors: list[dict[str, Any]],
    ) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.imports_table).values(
                dataset=dataset, source=source, status=status, total_rows=total_rows,
                imported_rows=imported_rows, error_rows=len(errors),
                errors_json=json.dumps(errors), created_at=_now(),
            ))
            return int(result.inserted_primary_key[0])

    def import_history(self, limit: int = 20) -> list[dict[str, Any]]:
        statement = select(self.imports_table).order_by(self.imports_table.c.id.desc()).limit(max(1, min(limit, 200)))
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        result = []
        for row in rows:
            item = _serialize(dict(row))
            item["errors"] = json.loads(item.pop("errors_json"))
            result.append(item)
        return result

    def indicator(
        self,
        indicator: IndicatorSchema,
        filters: dict[str, Any] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        dataset = self.config.datasets[indicator.dataset]
        table = self._dataset_table(dataset)
        conditions = []
        applied_filters = {**indicator.filters, **(filters or {})}
        for name, value in applied_filters.items():
            if name not in dataset.fields:
                raise ValueError(f"Unknown filter field '{name}'.")
            conditions.append(table.c[name] == _coerce(name, value, dataset.fields[name]))
        if start or end:
            if not indicator.date_field:
                raise ValueError(f"Indicator '{indicator.name}' does not define date_field.")
            date_schema = dataset.fields[indicator.date_field]
            if start:
                conditions.append(table.c[indicator.date_field] >= _coerce(indicator.date_field, start, date_schema))
            if end:
                conditions.append(table.c[indicator.date_field] <= _coerce(indicator.date_field, end, date_schema))

        if indicator.operation == "count":
            expression = func.count(table.c.id)
        elif indicator.operation == "sum":
            expression = func.sum(table.c[indicator.field])
        elif indicator.operation == "average":
            expression = func.avg(table.c[indicator.field])
        else:
            numerator = func.sum(table.c[indicator.numerator])
            denominator = func.sum(table.c[indicator.denominator])
            expression = numerator * indicator.multiplier / func.nullif(denominator, 0)
        statement = select(expression)
        if conditions:
            statement = statement.where(and_(*conditions))
        with self.engine.connect() as connection:
            value = connection.execute(statement).scalar_one()
        return {
            "name": indicator.name,
            "label": indicator.label,
            "dataset": indicator.dataset,
            "operation": indicator.operation,
            "value": float(value) if value is not None else None,
            "multiplier": indicator.multiplier,
            "filters": applied_filters,
            "period": {"start": start, "end": end},
        }

    def data_quality(self, rule: DataQualityRuleSchema) -> dict[str, Any]:
        dataset = self.config.datasets[rule.dataset]
        table = self._dataset_table(dataset)
        column = table.c[rule.field]
        if rule.check == "required":
            violation = column.is_(None)
            if dataset.fields[rule.field].type in {"string", "location"}:
                violation = or_(violation, column == "")
        elif rule.check == "range":
            bounds = []
            if rule.minimum is not None:
                bounds.append(column < rule.minimum)
            if rule.maximum is not None:
                bounds.append(column > rule.maximum)
            violation = and_(column.is_not(None), or_(*bounds))
        else:
            violation = and_(column.is_not(None), column.not_in(rule.values))
        with self.engine.connect() as connection:
            total = int(connection.execute(select(func.count(table.c.id))).scalar_one())
            violations = int(connection.execute(
                select(func.count(table.c.id)).where(violation)
            ).scalar_one())
        valid = total - violations
        return {
            "name": rule.name, "label": rule.label, "dataset": rule.dataset,
            "field": rule.field, "check": rule.check, "total": total,
            "valid": valid, "violations": violations,
            "score": (valid / total * 100) if total else None,
        }

    def dimension(self, dimension: DimensionSchema, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        dataset = self.config.datasets[dimension.dataset]
        table = self._dataset_table(dataset)
        conditions = []
        for name, value in (filters or {}).items():
            if name not in dataset.fields:
                raise ValueError(f"Unknown filter field '{name}'.")
            conditions.append(table.c[name] == _coerce(name, value, dataset.fields[name]))
        field = table.c[dimension.field]
        statement = select(field.label("value"), func.count(table.c.id).label("count")).group_by(field).order_by(field)
        if conditions:
            statement = statement.where(and_(*conditions))
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return {
            "name": dimension.name, "label": dimension.label, "dataset": dimension.dataset,
            "field": dimension.field, "filters": filters or {},
            "values": [{"value": _serialize(row["value"]), "count": int(row["count"])} for row in rows],
        }


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
        if schema.type in {"integer", "age"}:
            if isinstance(value, bool):
                raise ValueError
            if schema.type == "age" and isinstance(value, float) and not value.is_integer():
                raise ValueError
            result = int(value)
            if schema.type == "age" and not 0 <= result <= 130:
                raise ValueError
            return result
        if schema.type == "number":
            return float(value)
        if schema.type == "boolean":
            if isinstance(value, str):
                normalized = value.lower()
                if normalized not in {"true", "false", "1", "0"}:
                    raise ValueError
                return normalized in {"true", "1"}
            return bool(value)
        if schema.type == "date":
            return date.fromisoformat(str(value)[:10])
        if schema.type == "datetime":
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        result = str(value).strip()
        if schema.type in {"identifier", "disease_code", "organisation_unit", "facility"} and not result:
            raise ValueError
        if schema.type == "sex" and result.lower() not in {"female", "male", "intersex", "unknown"}:
            raise ValueError
        if schema.type == "case_classification" and result.lower() not in {
            "suspected", "probable", "confirmed", "discarded",
        }:
            raise ValueError
        if schema.type in {"sex", "case_classification"}:
            result = result.lower()
        if schema.type == "epi_week":
            if "-W" not in result:
                raise ValueError
            start, _ = resolve_period(result)
            if start.isocalendar().weekday != 1:
                raise ValueError
        if schema.type == "reporting_period":
            resolve_period(result)
        return result
    except (TypeError, ValueError) as error:
        raise ValueError(f"Field '{name}' must be a valid {schema.type}.") from error


def _type_key(value: Any) -> str:
    if isinstance(value, Boolean):
        return "boolean"
    if isinstance(value, DateTime):
        return "datetime"
    if isinstance(value, Date):
        return "date"
    if isinstance(value, Integer):
        return "integer"
    if isinstance(value, Float):
        return "number"
    if isinstance(value, (String, Text)):
        return "string"
    return str(value).lower()


def _compatible_type(configured: str, actual: str, dialect: str) -> bool:
    storage_type = "integer" if configured == "age" else ("string" if configured in TEXT_TYPES else configured)
    if storage_type == actual:
        return True
    # PHFrame 0.2.0a1 stored temporal values as SQLite TEXT and booleans as INTEGER.
    legacy_sqlite = {
        "date": "string",
        "datetime": "string",
        "boolean": "integer",
    }
    return dialect == "sqlite" and legacy_sqlite.get(storage_type) == actual


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _now() -> datetime:
    return datetime.now().astimezone()
