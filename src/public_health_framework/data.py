"""Data loading, validation, and public-health-oriented profiling."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from defusedxml import ElementTree

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm", ".json", ".xml"}


@dataclass(frozen=True)
class DashboardConfig:
    location: str | None = None
    date: str | None = None
    value: str | None = None
    population: str | None = None
    category: str | None = None


def load_dataset(path: str | Path, sheet: str | int | None = 0) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Input file does not exist: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type '{source.suffix}'. Use: {supported}")

    suffix = source.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(source)
    elif suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(source, sheet_name=sheet)
    elif suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            payload = next(
                (payload[key] for key in ("data", "records", "results", "items") if isinstance(payload.get(key), list)),
                [payload],
            )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError("JSON imports require an array of objects or a data/records/results/items array.")
        frame = pd.json_normalize(payload, sep=".")
    else:
        try:
            root = ElementTree.parse(source).getroot()
        except ElementTree.ParseError as error:
            raise ValueError(f"Invalid XML file: {error}") from error
        rows = list(root)
        frame = pd.DataFrame([_xml_record(row) for row in rows])

    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty:
        raise ValueError("The input file contains no data rows.")
    if not len(set(frame.columns)) == len(frame.columns):
        raise ValueError("Column names must be unique after surrounding spaces are removed.")
    return frame


def _xml_record(element: ElementTree.Element, prefix: str = "") -> dict[str, object]:
    record: dict[str, object] = {}
    for child in element:
        name = f"{prefix}.{child.tag}" if prefix else child.tag
        if list(child):
            record.update(_xml_record(child, name))
        else:
            record[name] = (child.text or "").strip() or None
    return record


def validate_config(frame: pd.DataFrame, config: DashboardConfig) -> None:
    selected = [
        config.location,
        config.date,
        config.value,
        config.population,
        config.category,
    ]
    missing = [name for name in selected if name and name not in frame.columns]
    if missing:
        raise ValueError(f"Columns not found: {', '.join(missing)}")


def prepare_dataset(frame: pd.DataFrame, config: DashboardConfig) -> pd.DataFrame:
    prepared = frame.copy()
    if config.date:
        prepared[config.date] = pd.to_datetime(prepared[config.date], errors="coerce")
    for column in (config.value, config.population):
        if column:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared
