"""Country-neutral geographic hierarchy discovery and validation."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any


LEVEL_HINTS = {
    "country": 0, "nation": 0, "adm0": 0,
    "region": 1, "province": 1, "state": 1, "adm1": 1,
    "district": 2, "county": 2, "adm2": 2,
    "subdistrict": 3, "upazila": 3, "commune": 3, "ward": 3, "adm3": 3,
    "village": 4, "community": 4, "adm4": 4,
    "facility": 5, "site": 5, "clinic": 5,
}


def infer_geography(rows: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    columns = profile.get("columns", []); candidates = []
    for column in columns:
        name = column["name"]; normalized = re.sub(r"[^a-z0-9]", "", name.casefold())
        hint = next(((label, rank) for label, rank in LEVEL_HINTS.items() if label in normalized), None)
        if column["semantic_type"] in {"location", "organisation_unit"} or hint:
            candidates.append({"field": name, "label": name.replace("_", " ").title(), "rank": hint[1] if hint else 99, "kind": hint[0] if hint else "administrative_area", "distinct": column["distinct"], "confidence": max(column["confidence"], .9 if hint else .65)})
    candidates.sort(key=lambda item: (item["rank"], item["distinct"]))
    unknown = [item for item in candidates if item["rank"] == 99]
    known = [item for item in candidates if item["rank"] != 99]
    if unknown:
        start = (max((item["rank"] for item in known), default=-1) + 1)
        for index, item in enumerate(sorted(unknown, key=lambda value: value["distinct"])): item["rank"] = start + index
    levels = sorted(candidates, key=lambda item: item["rank"])
    issues = []
    for parent, child in zip(levels, levels[1:]):
        parents: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            child_value, parent_value = row.get(child["field"]), row.get(parent["field"])
            if child_value not in {None, ""} and parent_value not in {None, ""}: parents[str(child_value)].add(str(parent_value))
        conflicts = {key: sorted(value) for key, value in parents.items() if len(value) > 1}
        if conflicts: issues.append({"rule": "multiple_parents", "severity": "error", "parent_field": parent["field"], "child_field": child["field"], "affected_count": len(conflicts), "examples": dict(list(conflicts.items())[:20])})
    latitude = next((item["name"] for item in columns if item["semantic_type"] == "latitude"), None)
    longitude = next((item["name"] for item in columns if item["semantic_type"] == "longitude"), None)
    geometry = next((item["name"] for item in columns if item["semantic_type"] == "geometry"), None)
    coordinate_rows = sum(row.get(latitude) not in {None, ""} and row.get(longitude) not in {None, ""} for row in rows) if latitude and longitude else 0
    geometry_rows = sum(row.get(geometry) not in {None, ""} for row in rows) if geometry else 0
    coverage = round(max(coordinate_rows, geometry_rows) / max(1, len(rows)) * 100, 2)
    return {"levels": levels, "latitude_field": latitude, "longitude_field": longitude, "geometry_field": geometry, "coordinate_rows": coordinate_rows, "geometry_rows": geometry_rows, "map_coverage_percent": coverage, "map_ready": bool((latitude and longitude) or geometry or levels), "issues": issues, "filter_fields": [item["field"] for item in levels]}
