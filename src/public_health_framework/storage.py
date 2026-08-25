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
        self.syncs_table = Table(
            "_phframe_syncs", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("connector", String(255), nullable=False),
            Column("dataset", String(255), nullable=False),
            Column("status", String(32), nullable=False),
            Column("fetched_rows", Integer, nullable=False),
            Column("imported_rows", Integer, nullable=False),
            Column("errors_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.mappings_table = Table(
            "_phframe_mappings", self.metadata,
            Column("name", String(255), primary_key=True),
            Column("dataset", String(255), nullable=False),
            Column("mapping_json", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.dataset_versions_table = Table(
            "_phframe_dataset_versions", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("dataset", String(255), nullable=False),
            Column("source", Text, nullable=False),
            Column("source_kind", String(64), nullable=False),
            Column("status", String(32), nullable=False),
            Column("row_count", Integer, nullable=False),
            Column("column_count", Integer, nullable=False),
            Column("content_digest", String(64), nullable=False),
            Column("schema_signature", String(64), nullable=False),
            Column("profile_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("approved_at", DateTime(timezone=True)),
        )
        self.staged_rows_table = Table(
            "_phframe_staged_rows", self.metadata,
            Column("version_id", Integer, primary_key=True),
            Column("row_number", Integer, primary_key=True),
            Column("data_json", Text, nullable=False),
        )
        self.column_profiles_table = Table(
            "_phframe_column_profiles", self.metadata,
            Column("version_id", Integer, primary_key=True),
            Column("column_name", String(255), primary_key=True),
            Column("storage_type", String(32), nullable=False),
            Column("semantic_type", String(64), nullable=False),
            Column("confidence", Float, nullable=False),
            Column("profile_json", Text, nullable=False),
        )
        self.quality_runs_table = Table(
            "_phframe_quality_runs", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("version_id", Integer, nullable=False), Column("score", Float, nullable=False),
            Column("readiness", String(32), nullable=False), Column("issue_count", Integer, nullable=False),
            Column("blocker_count", Integer, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.quality_issues_table = Table(
            "_phframe_quality_issues", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("run_id", Integer, nullable=False),
            Column("rule", String(64), nullable=False), Column("severity", String(16), nullable=False),
            Column("field", String(255)), Column("affected_count", Integer, nullable=False),
            Column("message", Text, nullable=False), Column("rows_json", Text, nullable=False),
            Column("evidence_json", Text, nullable=False),
        )
        self.transformations_table = Table(
            "_phframe_transformations", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("source_version_id", Integer, nullable=False), Column("output_version_id", Integer),
            Column("recipe", String(64), nullable=False), Column("status", String(32), nullable=False),
            Column("actor", String(255), nullable=False), Column("reason", Text, nullable=False),
            Column("options_json", Text, nullable=False), Column("summary_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.geography_models_table = Table(
            "_phframe_geography_models", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("version_id", Integer, nullable=False),
            Column("model_json", Text, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.semantic_models_table = Table(
            "_phframe_semantic_models", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("version_id", Integer, nullable=False),
            Column("contract_version", Integer, nullable=False), Column("status", String(32), nullable=False),
            Column("model_json", Text, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
            Column("approved_at", DateTime(timezone=True)),
        )
        self.generated_dashboards_table = Table(
            "_phframe_generated_dashboards", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("version_id", Integer, nullable=False),
            Column("semantic_model_id", Integer, nullable=False), Column("variant", String(32), nullable=False),
            Column("status", String(32), nullable=False), Column("spec_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False), Column("approved_at", DateTime(timezone=True)),
        )
        self.ai_summaries_table = Table(
            "_phframe_ai_summaries", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("title", String(255), nullable=False),
            Column("purpose", Text, nullable=False),
            Column("status", String(32), nullable=False),
            Column("content", Text, nullable=False),
            Column("provider", String(64), nullable=False),
            Column("model", String(255), nullable=False),
            Column("evidence_json", Text, nullable=False),
            Column("evidence_digest", String(64), nullable=False),
            Column("privacy_json", Text, nullable=False),
            Column("created_by", String(255), nullable=False),
            Column("reviewed_by", String(255)),
            Column("review_note", Text),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("reviewed_at", DateTime(timezone=True)),
        )
        self.ai_audit_table = Table(
            "_phframe_ai_audit", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("summary_id", Integer),
            Column("event", String(64), nullable=False),
            Column("actor", String(255), nullable=False),
            Column("details_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.ai_chat_table = Table(
            "_phframe_ai_chat", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(64), nullable=False),
            Column("question", Text, nullable=False),
            Column("answer", Text, nullable=False),
            Column("intent", String(64), nullable=False),
            Column("evidence_json", Text, nullable=False),
            Column("evidence_digest", String(64), nullable=False),
            Column("privacy_json", Text, nullable=False),
            Column("actor", String(255), nullable=False),
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
        self.metadata.create_all(
            self.engine, tables=[self.schema_table, self.imports_table, self.syncs_table, self.mappings_table, self.dataset_versions_table, self.staged_rows_table, self.column_profiles_table, self.quality_runs_table, self.quality_issues_table, self.transformations_table, self.geography_models_table, self.semantic_models_table, self.generated_dashboards_table, self.ai_summaries_table, self.ai_audit_table, self.ai_chat_table]
        )
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

    def list(
        self, dataset: DatasetSchema, limit: int = 100, offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        table = self._dataset_table(dataset)
        statement = select(table).order_by(table.c.id.desc()).limit(max(1, min(limit, 1000))).offset(max(0, offset))
        for name, value in (filters or {}).items():
            if name not in dataset.fields:
                raise ValueError(f"Unknown filter field '{name}'.")
            statement = statement.where(table.c[name] == _coerce(name, value, dataset.fields[name]))
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_serialize(dict(row)) for row in rows]

    def count(self, dataset: DatasetSchema, filters: dict[str, Any] | None = None) -> int:
        table = self._dataset_table(dataset); statement = select(func.count()).select_from(table)
        for name, value in (filters or {}).items():
            if name not in dataset.fields: raise ValueError(f"Unknown filter field '{name}'.")
            statement = statement.where(table.c[name] == _coerce(name, value, dataset.fields[name]))
        with self.engine.connect() as connection: return int(connection.scalar(statement) or 0)

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

    def import_run(self, run_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.imports_table).where(self.imports_table.c.id == run_id)
            ).mappings().first()
        if not row:
            return None
        item = _serialize(dict(row))
        item["errors"] = json.loads(item.pop("errors_json"))
        return item

    def save_mapping(self, name: str, dataset: str, mapping: dict[str, str]) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(self.mappings_table).where(self.mappings_table.c.name == name))
            connection.execute(insert(self.mappings_table).values(
                name=name, dataset=dataset, mapping_json=json.dumps(mapping), updated_at=_now(),
            ))

    def mappings(self, dataset: str | None = None) -> list[dict[str, Any]]:
        statement = select(self.mappings_table)
        if dataset:
            statement = statement.where(self.mappings_table.c.dataset == dataset)
        statement = statement.order_by(self.mappings_table.c.name)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        result = []
        for row in rows:
            item = _serialize(dict(row))
            item["mapping"] = json.loads(item.pop("mapping_json"))
            result.append(item)
        return result

    def stage_dataset(self, dataset: str, source: str, source_kind: str, rows: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
        """Persist an immutable source version and its deterministic profile."""
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.dataset_versions_table).values(
                dataset=dataset, source=source, source_kind=source_kind, status="staged",
                row_count=profile["row_count"], column_count=profile["column_count"],
                content_digest=profile["content_digest"], schema_signature=profile["schema_signature"],
                profile_json=json.dumps(profile), created_at=now, approved_at=None,
            ))
            version_id = int(result.inserted_primary_key[0])
            if rows:
                connection.execute(insert(self.staged_rows_table), [
                    {"version_id": version_id, "row_number": index, "data_json": json.dumps(row)}
                    for index, row in enumerate(rows, start=1)
                ])
            if profile["columns"]:
                connection.execute(insert(self.column_profiles_table), [
                    {
                        "version_id": version_id, "column_name": item["name"],
                        "storage_type": item["storage_type"], "semantic_type": item["semantic_type"],
                        "confidence": item["confidence"], "profile_json": json.dumps(item),
                    }
                    for item in profile["columns"]
                ])
        return self.dataset_version(version_id) or {}

    def dataset_versions(self, dataset: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        statement = select(self.dataset_versions_table)
        if dataset: statement = statement.where(self.dataset_versions_table.c.dataset == dataset)
        statement = statement.order_by(self.dataset_versions_table.c.id.desc()).limit(max(1, min(limit, 200)))
        with self.engine.connect() as connection: rows = connection.execute(statement).mappings().all()
        return [self._version_row(row, include_profile=False) for row in rows]

    def dataset_version(self, version_id: int, include_rows: bool = False) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(self.dataset_versions_table).where(self.dataset_versions_table.c.id == version_id)).mappings().first()
            if not row: return None
            item = self._version_row(row, include_profile=True)
            if include_rows:
                staged = connection.execute(select(self.staged_rows_table).where(self.staged_rows_table.c.version_id == version_id).order_by(self.staged_rows_table.c.row_number)).mappings().all()
                item["rows"] = [json.loads(value["data_json"]) for value in staged]
        return item

    def staged_rows(self, version_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        statement = select(self.staged_rows_table).where(self.staged_rows_table.c.version_id == version_id).order_by(self.staged_rows_table.c.row_number).limit(max(1, min(limit, 1000))).offset(max(0, offset))
        with self.engine.connect() as connection: rows = connection.execute(statement).mappings().all()
        return [{"row_number": row["row_number"], "data": json.loads(row["data_json"])} for row in rows]

    @staticmethod
    def _version_row(row: Any, include_profile: bool) -> dict[str, Any]:
        item = _serialize(dict(row))
        raw_profile = item.pop("profile_json")
        if include_profile: item["profile"] = json.loads(raw_profile)
        return item

    def approve_dataset_version(self, version_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            result = connection.execute(update(self.dataset_versions_table).where(self.dataset_versions_table.c.id == version_id).values(status="approved", approved_at=_now()))
        return self.dataset_version(version_id) if result.rowcount else None

    def transition_dataset_version(self, version_id: int, status: str) -> dict[str, Any] | None:
        if status not in {"staged", "approved", "rejected", "archived"}: raise ValueError("Invalid dataset version status.")
        current = self.dataset_version(version_id)
        if not current: return None
        allowed = {"staged": {"approved", "rejected"}, "approved": {"archived"}, "rejected": {"archived"}, "archived": set()}
        if status != current["status"] and status not in allowed[current["status"]]:
            raise ValueError(f"Cannot change dataset version from {current['status']} to {status}.")
        with self.engine.begin() as connection:
            connection.execute(update(self.dataset_versions_table).where(self.dataset_versions_table.c.id == version_id).values(status=status, approved_at=_now() if status == "approved" else current["approved_at"]))
        return self.dataset_version(version_id)

    def record_quality_run(self, version_id: int, report: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.quality_runs_table).values(version_id=version_id, score=report["score"], readiness=report["readiness"], issue_count=report["issue_count"], blocker_count=report["blocker_count"], created_at=_now()))
            run_id = int(result.inserted_primary_key[0])
            if report["issues"]: connection.execute(insert(self.quality_issues_table), [{"run_id": run_id, "rule": item["rule"], "severity": item["severity"], "field": item["field"], "affected_count": item["affected_count"], "message": item["message"], "rows_json": json.dumps(item["rows"]), "evidence_json": json.dumps(item["evidence"])} for item in report["issues"]])
        return self.quality_run(run_id) or {}

    def quality_run(self, run_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(self.quality_runs_table).where(self.quality_runs_table.c.id == run_id)).mappings().first()
            if not row: return None
            issues = connection.execute(select(self.quality_issues_table).where(self.quality_issues_table.c.run_id == run_id).order_by(self.quality_issues_table.c.id)).mappings().all()
        item = _serialize(dict(row)); item["issues"] = []
        for issue in issues:
            value = _serialize(dict(issue)); value["rows"] = json.loads(value.pop("rows_json")); value["evidence"] = json.loads(value.pop("evidence_json")); item["issues"].append(value)
        return item

    def latest_quality_run(self, version_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection: run_id = connection.scalar(select(self.quality_runs_table.c.id).where(self.quality_runs_table.c.version_id == version_id).order_by(self.quality_runs_table.c.id.desc()).limit(1))
        return self.quality_run(int(run_id)) if run_id else None

    def record_transformation(self, source_version_id: int, output_version_id: int | None, recipe: str, status: str, actor: str, reason: str, options: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.transformations_table).values(source_version_id=source_version_id, output_version_id=output_version_id, recipe=recipe, status=status, actor=actor, reason=reason, options_json=json.dumps(options), summary_json=json.dumps(summary), created_at=_now()))
            transformation_id = int(result.inserted_primary_key[0])
        return self.transformation(transformation_id) or {}

    def transformation(self, transformation_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection: row = connection.execute(select(self.transformations_table).where(self.transformations_table.c.id == transformation_id)).mappings().first()
        if not row: return None
        item = _serialize(dict(row)); item["options"] = json.loads(item.pop("options_json")); item["summary"] = json.loads(item.pop("summary_json")); return item

    def transformations(self, version_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        statement = select(self.transformations_table)
        if version_id: statement = statement.where(or_(self.transformations_table.c.source_version_id == version_id, self.transformations_table.c.output_version_id == version_id))
        statement = statement.order_by(self.transformations_table.c.id.desc()).limit(max(1, min(limit, 500)))
        with self.engine.connect() as connection: rows = connection.execute(statement).mappings().all()
        result = []
        for row in rows:
            item = _serialize(dict(row)); item["options"] = json.loads(item.pop("options_json")); item["summary"] = json.loads(item.pop("summary_json")); result.append(item)
        return result

    def record_geography_model(self, version_id: int, model: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.geography_models_table).values(version_id=version_id, model_json=json.dumps(model), created_at=_now())); model_id = int(result.inserted_primary_key[0])
        return self.geography_model(version_id, model_id) or {}

    def geography_model(self, version_id: int, model_id: int | None = None) -> dict[str, Any] | None:
        statement = select(self.geography_models_table).where(self.geography_models_table.c.version_id == version_id)
        if model_id: statement = statement.where(self.geography_models_table.c.id == model_id)
        statement = statement.order_by(self.geography_models_table.c.id.desc()).limit(1)
        with self.engine.connect() as connection: row = connection.execute(statement).mappings().first()
        if not row: return None
        item = _serialize(dict(row)); item["model"] = json.loads(item.pop("model_json")); return item

    def record_semantic_model(self, version_id: int, model: dict[str, Any]) -> dict[str, Any]:
        with self.engine.connect() as connection: previous = connection.scalar(select(func.max(self.semantic_models_table.c.contract_version)).where(self.semantic_models_table.c.version_id == version_id))
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.semantic_models_table).values(version_id=version_id, contract_version=int(previous or 0) + 1, status="draft", model_json=json.dumps(model), created_at=_now(), approved_at=None)); model_id = int(result.inserted_primary_key[0])
        return self.semantic_model(version_id, model_id) or {}

    def semantic_model(self, version_id: int, model_id: int | None = None) -> dict[str, Any] | None:
        statement = select(self.semantic_models_table).where(self.semantic_models_table.c.version_id == version_id)
        if model_id: statement = statement.where(self.semantic_models_table.c.id == model_id)
        statement = statement.order_by(self.semantic_models_table.c.id.desc()).limit(1)
        with self.engine.connect() as connection: row = connection.execute(statement).mappings().first()
        if not row: return None
        item = _serialize(dict(row)); item["model"] = json.loads(item.pop("model_json")); return item

    def approve_semantic_model(self, version_id: int, model_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            connection.execute(update(self.semantic_models_table).where(and_(self.semantic_models_table.c.version_id == version_id, self.semantic_models_table.c.status == "approved")).values(status="superseded"))
            result = connection.execute(update(self.semantic_models_table).where(and_(self.semantic_models_table.c.id == model_id, self.semantic_models_table.c.version_id == version_id, self.semantic_models_table.c.status == "draft")).values(status="approved", approved_at=_now()))
        return self.semantic_model(version_id, model_id) if result.rowcount else None

    def record_generated_dashboard(self, version_id: int, semantic_model_id: int, variant: str, spec: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.generated_dashboards_table).values(version_id=version_id, semantic_model_id=semantic_model_id, variant=variant, status="draft", spec_json=json.dumps(spec), created_at=_now(), approved_at=None))
            item_id = int(result.inserted_primary_key[0])
        return self.generated_dashboard(version_id, item_id) or {}

    def generated_dashboard(self, version_id: int, dashboard_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection: row = connection.execute(select(self.generated_dashboards_table).where(and_(self.generated_dashboards_table.c.version_id == version_id, self.generated_dashboards_table.c.id == dashboard_id))).mappings().first()
        if not row: return None
        item = _serialize(dict(row)); item["spec"] = json.loads(item.pop("spec_json")); return item

    def generated_dashboards(self, version_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as connection: rows = connection.execute(select(self.generated_dashboards_table).where(self.generated_dashboards_table.c.version_id == version_id).order_by(self.generated_dashboards_table.c.id.desc())).mappings().all()
        result = []
        for row in rows:
            item = _serialize(dict(row)); item["spec"] = json.loads(item.pop("spec_json")); result.append(item)
        return result

    def approve_generated_dashboard(self, version_id: int, dashboard_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection: result = connection.execute(update(self.generated_dashboards_table).where(and_(self.generated_dashboards_table.c.version_id == version_id, self.generated_dashboards_table.c.id == dashboard_id, self.generated_dashboards_table.c.status == "draft")).values(status="approved", approved_at=_now()))
        return self.generated_dashboard(version_id, dashboard_id) if result.rowcount else None

    def create_ai_summary(self, values: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.ai_summaries_table).values(**values, status="draft", created_at=now))
            summary_id = int(result.inserted_primary_key[0])
            connection.execute(insert(self.ai_audit_table).values(summary_id=summary_id, event="generated", actor=values["created_by"], details_json=json.dumps({"provider": values["provider"], "model": values["model"], "evidence_digest": values["evidence_digest"]}), created_at=now))
        return self.ai_summary(summary_id) or {}

    def ai_summary(self, summary_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(self.ai_summaries_table).where(self.ai_summaries_table.c.id == summary_id)).mappings().first()
        return self._ai_summary_row(row) if row else None

    def ai_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.ai_summaries_table).order_by(self.ai_summaries_table.c.id.desc()).limit(max(1, min(limit, 200)))).mappings().all()
        return [self._ai_summary_row(row) for row in rows]

    @staticmethod
    def _ai_summary_row(row: Any) -> dict[str, Any]:
        item = _serialize(dict(row))
        item["evidence"] = json.loads(item.pop("evidence_json")); item["privacy"] = json.loads(item.pop("privacy_json"))
        return item

    def review_ai_summary(self, summary_id: int, decision: str, actor: str, note: str) -> dict[str, Any] | None:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected.")
        current = self.ai_summary(summary_id)
        if not current:
            return None
        if current["status"] != "draft":
            raise ValueError("Only draft summaries can be reviewed.")
        now = _now()
        with self.engine.begin() as connection:
            connection.execute(update(self.ai_summaries_table).where(self.ai_summaries_table.c.id == summary_id).values(status=decision, reviewed_by=actor, review_note=note, reviewed_at=now))
            connection.execute(insert(self.ai_audit_table).values(summary_id=summary_id, event=decision, actor=actor, details_json=json.dumps({"note": note}), created_at=now))
        return self.ai_summary(summary_id)

    def ai_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.ai_audit_table).order_by(self.ai_audit_table.c.id.desc()).limit(max(1, min(limit, 500)))).mappings().all()
        result = []
        for row in rows:
            item = _serialize(dict(row)); item["details"] = json.loads(item.pop("details_json")); result.append(item)
        return result

    def record_ai_chat(self, values: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.ai_chat_table).values(**values, created_at=now))
            chat_id = int(result.inserted_primary_key[0])
            connection.execute(insert(self.ai_audit_table).values(summary_id=None, event="analyst_question", actor=values["actor"], details_json=json.dumps({"chat_id": chat_id, "session_id": values["session_id"], "intent": values["intent"], "evidence_digest": values["evidence_digest"]}), created_at=now))
        return self.ai_chat(chat_id) or {}

    def ai_chat(self, chat_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(self.ai_chat_table).where(self.ai_chat_table.c.id == chat_id)).mappings().first()
        return self._ai_chat_row(row) if row else None

    def ai_chats(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.ai_chat_table).where(self.ai_chat_table.c.session_id == session_id).order_by(self.ai_chat_table.c.id.asc()).limit(max(1, min(limit, 200)))).mappings().all()
        return [self._ai_chat_row(row) for row in rows]

    @staticmethod
    def _ai_chat_row(row: Any) -> dict[str, Any]:
        item = _serialize(dict(row)); item["evidence"] = json.loads(item.pop("evidence_json")); item["privacy"] = json.loads(item.pop("privacy_json")); return item

    def record_sync(
        self, connector: str, dataset: str, status: str, fetched_rows: int,
        imported_rows: int, errors: list[dict[str, Any]],
    ) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(insert(self.syncs_table).values(
                connector=connector, dataset=dataset, status=status, fetched_rows=fetched_rows,
                imported_rows=imported_rows, errors_json=json.dumps(errors), created_at=_now(),
            ))
            return int(result.inserted_primary_key[0])

    def sync_history(self, limit: int = 20, connector: str | None = None) -> list[dict[str, Any]]:
        statement = select(self.syncs_table)
        if connector:
            statement = statement.where(self.syncs_table.c.connector == connector)
        statement = statement.order_by(self.syncs_table.c.id.desc()).limit(max(1, min(limit, 200)))
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

    def epi_curve(
        self, dataset: DatasetSchema, date_field: str, value_field: str | None = None
    ) -> list[dict[str, Any]]:
        if date_field not in dataset.fields or dataset.fields[date_field].type not in {"date", "datetime"}:
            raise ValueError("date_field must identify a date or datetime field.")
        if value_field and (
            value_field not in dataset.fields or dataset.fields[value_field].type not in {"integer", "number"}
        ):
            raise ValueError("value_field must identify an integer or number field.")
        table = self._dataset_table(dataset)
        date_column = table.c[date_field]
        measure = func.sum(table.c[value_field]) if value_field else func.count(table.c.id)
        statement = select(date_column.label("date"), measure.label("value")).where(
            date_column.is_not(None)
        ).group_by(date_column).order_by(date_column)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [{"date": _serialize(row["date"]), "value": float(row["value"])} for row in rows]


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
