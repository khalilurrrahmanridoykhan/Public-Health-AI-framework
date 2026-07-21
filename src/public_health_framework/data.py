"""Data loading, validation, and public-health-oriented profiling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}


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

    if source.suffix.lower() == ".csv":
        frame = pd.read_csv(source)
    else:
        frame = pd.read_excel(source, sheet_name=sheet)

    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty:
        raise ValueError("The input file contains no data rows.")
    if not len(set(frame.columns)) == len(frame.columns):
        raise ValueError("Column names must be unique after surrounding spaces are removed.")
    return frame


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

