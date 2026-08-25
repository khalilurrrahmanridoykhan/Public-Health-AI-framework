"""Deterministic dataset profiling for the governed ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

import pandas as pd


MISSING_MARKERS = {"", "-", "--", "n/a", "na", "null", "none", "unknown"}
IDENTIFIER_NAMES = re.compile(r"(^id$|_id$|^uid$|_uid$|code$|number$)", re.I)
DATE_NAMES = re.compile(r"(date|time|period|month|year|week)", re.I)
LOCATION_NAMES = re.compile(r"(country|region|district|province|county|facility|location|org.?unit|ward|village)", re.I)


def profile_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Return a JSON-safe, reproducible profile and semantic suggestions."""
    normalized = frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    columns = [profile_series(name, normalized[name]) for name in normalized.columns]
    rows = [_json_value(row) for row in normalized.to_dict(orient="records")]
    schema = [{"name": item["name"], "storage_type": item["storage_type"], "semantic_type": item["semantic_type"]} for item in columns]
    duplicate_rows = int(normalized.fillna("__PHFRAME_NULL__").duplicated(keep=False).sum())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(normalized)),
        "column_count": int(len(normalized.columns)),
        "duplicate_rows": duplicate_rows,
        "schema_signature": hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest(),
        "content_digest": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "columns": columns,
    }


def profile_series(name: str, series: pd.Series) -> dict[str, Any]:
    values = series.map(_json_value)
    present = values[~values.map(_missing)]
    total = int(len(values)); non_null = int(len(present)); distinct = int(present.nunique(dropna=True))
    storage, type_confidence = _storage_type(present)
    semantic, semantic_confidence, candidates = _semantic_type(name, present, storage, distinct)
    result: dict[str, Any] = {
        "name": name,
        "storage_type": storage,
        "semantic_type": semantic,
        "confidence": round(min(type_confidence, semantic_confidence), 3),
        "candidates": candidates,
        "total": total,
        "non_null": non_null,
        "missing": total - non_null,
        "missing_percent": round(((total - non_null) / total * 100) if total else 0, 2),
        "distinct": distinct,
        "unique_percent": round((distinct / non_null * 100) if non_null else 0, 2),
        "examples": list(dict.fromkeys(str(value)[:160] for value in present.head(20)))[:5],
    }
    numeric = pd.to_numeric(present, errors="coerce").dropna()
    if len(numeric) and storage in {"integer", "number"}:
        result["minimum"] = _finite(numeric.min()); result["maximum"] = _finite(numeric.max())
        result["mean"] = _finite(numeric.mean())
    lengths = present.map(lambda value: len(str(value)))
    if len(lengths):
        result["minimum_length"] = int(lengths.min()); result["maximum_length"] = int(lengths.max())
    return result


def _storage_type(values: pd.Series) -> tuple[str, float]:
    if values.empty: return "string", 0.25
    lowered = values.astype(str).str.strip().str.lower()
    if lowered.isin({"true", "false", "yes", "no", "0", "1"}).all(): return "boolean", 0.98
    numeric = pd.to_numeric(values, errors="coerce")
    ratio = float(numeric.notna().mean())
    if ratio >= 0.95:
        whole = numeric.dropna().map(lambda value: float(value).is_integer()).all()
        return ("integer" if whole else "number"), ratio
    parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    date_ratio = float(parsed.notna().mean())
    if date_ratio >= 0.9:
        has_time = values.astype(str).str.contains(r"T|\d:\d", regex=True).any()
        return ("datetime" if has_time else "date"), date_ratio
    if values.map(lambda value: isinstance(value, (dict, list))).mean() >= 0.9: return "json", 0.95
    return "string", max(0.6, 1 - max(ratio, date_ratio))


def _semantic_type(name: str, values: pd.Series, storage: str, distinct: int) -> tuple[str, float, list[dict[str, Any]]]:
    lower = name.lower().strip().replace(" ", "_")
    count = max(1, len(values)); unique_ratio = distinct / count
    ranked: list[tuple[str, float]] = []
    if "latitude" in lower or lower in {"lat", "y"}: ranked.append(("latitude", 0.99))
    if "longitude" in lower or lower in {"lon", "lng", "x"}: ranked.append(("longitude", 0.99))
    if "geometry" in lower or "polygon" in lower or "geojson" in lower: ranked.append(("geometry", 0.98))
    if DATE_NAMES.search(lower): ranked.append(("reporting_period" if "period" in lower or "week" in lower else storage if storage in {"date", "datetime"} else "date", 0.92))
    if LOCATION_NAMES.search(lower): ranked.append(("organisation_unit" if "org" in lower or "facility" in lower else "location", 0.9))
    if IDENTIFIER_NAMES.search(lower) or (storage == "string" and unique_ratio > 0.95): ranked.append(("identifier", 0.96 if IDENTIFIER_NAMES.search(lower) else 0.68))
    if storage in {"integer", "number"}: ranked.append(("measure", 0.82))
    if storage == "boolean": ranked.append(("boolean", 0.98))
    if storage == "string" and distinct <= min(30, max(2, int(count * 0.2))): ranked.append(("category", 0.84))
    ranked.append(((storage if storage != "json" else "structured_data"), 0.7))
    deduped: dict[str, float] = {}
    for candidate, confidence in ranked: deduped[candidate] = max(confidence, deduped.get(candidate, 0))
    ordered = sorted(deduped.items(), key=lambda item: item[1], reverse=True)
    return ordered[0][0], ordered[0][1], [{"type": item[0], "confidence": round(item[1], 3)} for item in ordered[:3]]


def _missing(value: Any) -> bool:
    if value is None or (isinstance(value, str) and value.strip().lower() in MISSING_MARKERS): return True
    try: return bool(pd.isna(value))
    except (TypeError, ValueError): return False


def _json_value(value: Any) -> Any:
    if value is None or (not isinstance(value, (dict, list)) and pd.isna(value)): return None
    if isinstance(value, (pd.Timestamp, datetime)): return value.isoformat()
    if hasattr(value, "item"): return value.item()
    return value


def _finite(value: Any) -> float | int | None:
    number = float(value)
    if not math.isfinite(number): return None
    return int(number) if number.is_integer() else round(number, 6)
