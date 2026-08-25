"""Deterministic quality checks for immutable staged dataset versions."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from typing import Any

import pandas as pd


WEIGHTS = {"critical": 20, "error": 8, "warning": 3, "info": 1}


def evaluate_quality(rows: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    columns = {item["name"]: item for item in profile["columns"]}
    frame = pd.DataFrame(rows)
    for name, column in columns.items():
        if column["missing"]:
            severity = "error" if column["missing_percent"] >= 50 else "warning"
            issues.append(_issue("missing_values", severity, name, None, column["missing"], f"{column['missing']} of {column['total']} values are missing.", {"missing_percent": column["missing_percent"]}))
        if column["storage_type"] in {"integer", "number"} and name in frame:
            numeric = pd.to_numeric(frame[name], errors="coerce")
            invalid = int((frame[name].notna() & numeric.isna()).sum())
            if invalid: issues.append(_issue("invalid_numeric", "error", name, None, invalid, "Values cannot be parsed as numbers."))
            valid = numeric.dropna()
            if len(valid) >= 8:
                q1, q3 = valid.quantile(.25), valid.quantile(.75); iqr = q3 - q1
                if iqr > 0:
                    mask = (numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)
                    count = int(mask.sum())
                    if count: issues.append(_issue("statistical_outlier", "warning", name, _rows(mask), count, "Values fall outside the 1.5×IQR review range.", {"lower": float(q1 - 1.5 * iqr), "upper": float(q3 + 1.5 * iqr)}))
        if column["storage_type"] in {"date", "datetime"} and name in frame:
            parsed = pd.to_datetime(frame[name], errors="coerce", utc=True, format="mixed")
            invalid_mask = frame[name].notna() & parsed.isna()
            if invalid_mask.any(): issues.append(_issue("invalid_date", "error", name, _rows(invalid_mask), int(invalid_mask.sum()), "Values cannot be parsed as dates."))
            future = parsed > datetime.now(timezone.utc)
            if future.any(): issues.append(_issue("future_date", "warning", name, _rows(future), int(future.sum()), "Dates occur in the future."))
        if column["semantic_type"] == "latitude" and name in frame: _range_issue(issues, frame, name, -90, 90)
        if column["semantic_type"] == "longitude" and name in frame: _range_issue(issues, frame, name, -180, 180)
        if column["semantic_type"] == "category" and name in frame:
            groups: dict[str, set[str]] = defaultdict(set)
            for value in frame[name].dropna().astype(str): groups[value.strip().casefold()].add(value)
            aliases = [sorted(values) for values in groups.values() if len(values) > 1]
            if aliases: issues.append(_issue("category_alias", "warning", name, None, sum(len(item) for item in aliases), "Category values differ only by case or surrounding whitespace.", {"groups": aliases[:20]}))
    serialized = [json.dumps(row, sort_keys=True, default=str) for row in rows]
    counts = Counter(serialized); duplicate_indexes = [index + 1 for index, value in enumerate(serialized) if counts[value] > 1]
    if duplicate_indexes: issues.append(_issue("duplicate_row", "error", None, duplicate_indexes[:500], len(duplicate_indexes), "Identical source rows were found."))
    penalty = sum(WEIGHTS[item["severity"]] * min(item["affected_count"], 10) for item in issues)
    score = max(0.0, round(100 - min(100, penalty / max(1, len(rows))), 1))
    blockers = sum(item["severity"] in {"critical", "error"} for item in issues)
    return {"score": score, "readiness": "blocked" if blockers else "ready_with_warnings" if issues else "ready", "issue_count": len(issues), "blocker_count": blockers, "issues": issues}


def _issue(rule: str, severity: str, field: str | None, rows: list[int] | None, count: int, message: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"rule": rule, "severity": severity, "field": field, "rows": rows or [], "affected_count": count, "message": message, "evidence": evidence or {}}


def _rows(mask: pd.Series) -> list[int]: return [int(index) + 1 for index, value in enumerate(mask.fillna(False)) if value][:500]


def _range_issue(issues: list[dict[str, Any]], frame: pd.DataFrame, name: str, low: float, high: float) -> None:
    numeric = pd.to_numeric(frame[name], errors="coerce"); mask = numeric.notna() & ((numeric < low) | (numeric > high))
    if mask.any(): issues.append(_issue("coordinate_range", "error", name, _rows(mask), int(mask.sum()), f"Coordinates must be between {low} and {high}.", {"minimum": low, "maximum": high}))
