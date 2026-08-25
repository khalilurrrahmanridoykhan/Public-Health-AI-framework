"""Atomic tabular imports into PHFrame datasets."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from defusedxml import ElementTree

import pandas as pd
import yaml

from .config import ProjectConfig
from .data import load_dataset
from .storage import Storage, validate_payload


@dataclass(frozen=True)
class ImportResult:
    run_id: int
    dataset: str
    total_rows: int
    imported_rows: int
    errors: tuple[dict[str, Any], ...]
    dry_run: bool

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        return "validated" if self.dry_run else "completed"


def load_mapping(path: str | Path) -> tuple[str | None, dict[str, str]]:
    source = Path(path)
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    columns = raw.get("columns", raw)
    if not isinstance(columns, dict):
        raise ValueError("Mapping file must define a 'columns' object.")
    return raw.get("dataset"), {str(source): str(target) for source, target in columns.items()}


def save_mapping(path: str | Path, dataset: str, mapping: dict[str, str]) -> Path:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump({"dataset": dataset, "columns": mapping}, sort_keys=False)
    destination.write_text(content, encoding="utf-8")
    return destination


def import_dataset(
    config: ProjectConfig,
    dataset_name: str,
    source: str | Path,
    mapping: dict[str, str] | None = None,
    sheet: str | int = 0,
    dry_run: bool = False,
) -> ImportResult:
    if dataset_name not in config.datasets:
        raise ValueError(f"Dataset not found: {dataset_name}")
    frame = load_dataset(source, sheet=sheet)
    return import_frame(config, dataset_name, frame, str(Path(source).resolve()), mapping, dry_run)


def load_uploaded_frame(content: bytes, filename: str, sheet: str | int = 0) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(BytesIO(content))
    elif suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(BytesIO(content), sheet_name=sheet)
    elif suffix == ".json":
        try:
            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid JSON file: {error}") from error
        if isinstance(payload, dict):
            payload = next(
                (payload[key] for key in ("data", "records", "results", "items") if isinstance(payload.get(key), list)),
                [payload],
            )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError("JSON imports require an array of objects or a data/records/results/items array.")
        frame = pd.json_normalize(payload, sep=".")
    elif suffix == ".xml":
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as error:
            raise ValueError(f"Invalid XML file: {error}") from error
        rows = list(root)
        if not rows:
            raise ValueError("XML imports require a root element containing record elements.")
        frame = pd.DataFrame([_xml_record(row) for row in rows])
    else:
        raise ValueError("Browser imports support .csv, .xlsx, .xlsm, .json, and .xml files.")
    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty:
        raise ValueError("The input file contains no data rows.")
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("Column names must be unique after surrounding spaces are removed.")
    return frame


def _xml_record(element: ElementTree.Element, prefix: str = "") -> dict[str, Any]:
    record: dict[str, Any] = {}
    for child in element:
        name = f"{prefix}.{child.tag}" if prefix else child.tag
        if list(child):
            record.update(_xml_record(child, name))
        else:
            record[name] = (child.text or "").strip() or None
    return record


def import_frame(
    config: ProjectConfig,
    dataset_name: str,
    frame: pd.DataFrame,
    source: str,
    mapping: dict[str, str] | None = None,
    dry_run: bool = False,
) -> ImportResult:
    if dataset_name not in config.datasets:
        raise ValueError(f"Dataset not found: {dataset_name}")
    dataset = config.datasets[dataset_name]
    storage = Storage(config)
    storage.initialize()
    mapping = mapping or {column: column for column in frame.columns if column in dataset.fields}
    unknown_sources = set(mapping) - set(frame.columns)
    unknown_targets = set(mapping.values()) - set(dataset.fields)
    if unknown_sources:
        raise ValueError(f"Mapped source columns not found: {', '.join(sorted(unknown_sources))}")
    if unknown_targets:
        raise ValueError(f"Mapped dataset fields not found: {', '.join(sorted(unknown_targets))}")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Each dataset field can only be mapped once.")

    payloads: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for position, (_, row) in enumerate(frame.iterrows(), start=2):
        payload = {target: _clean(row[source_name]) for source_name, target in mapping.items()}
        try:
            validate_payload(dataset, payload, partial=False)
            payloads.append(payload)
        except ValueError as error:
            errors.append({"row": position, "message": str(error)})

    imported = 0
    if not errors and not dry_run:
        try:
            imported = storage.bulk_create(dataset, payloads)
        except ValueError as error:
            errors.append({"row": 0, "message": str(error)})
    status = "failed" if errors else ("validated" if dry_run else "completed")
    run_id = storage.record_import(
        dataset_name, source, status, len(frame), imported, errors
    )
    return ImportResult(run_id, dataset_name, len(frame), imported, tuple(errors), dry_run)


def preview_frame(config: ProjectConfig, dataset_name: str, frame: pd.DataFrame) -> dict[str, Any]:
    if dataset_name not in config.datasets:
        raise ValueError(f"Dataset not found: {dataset_name}")
    fields = config.datasets[dataset_name].fields
    suggested = {column: column for column in frame.columns if column in fields}
    sample = [
        {str(name): _clean(value) for name, value in row.items()}
        for row in frame.head(10).to_dict(orient="records")
    ]
    return {
        "columns": [str(column) for column in frame.columns],
        "fields": [
            {"name": name, "type": schema.type, "required": schema.required, "label": schema.label or name}
            for name, schema in fields.items()
        ],
        "suggested_mapping": suggested,
        "sample": sample,
        "total_rows": len(frame),
    }


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value
