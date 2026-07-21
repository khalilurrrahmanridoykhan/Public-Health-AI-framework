"""Atomic tabular imports into PHFrame datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    dataset = config.datasets[dataset_name]
    storage = Storage(config)
    storage.initialize()
    frame = load_dataset(source, sheet=sheet)
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
        imported = storage.bulk_create(dataset, payloads)
    status = "failed" if errors else ("validated" if dry_run else "completed")
    run_id = storage.record_import(
        dataset_name, str(Path(source).resolve()), status, len(frame), imported, errors
    )
    return ImportResult(run_id, dataset_name, len(frame), imported, tuple(errors), dry_run)


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value

