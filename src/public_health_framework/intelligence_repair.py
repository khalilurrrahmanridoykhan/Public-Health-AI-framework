"""Previewable, deterministic repair recipes for staged data."""

from __future__ import annotations

import json
from typing import Any


SAFE_RECIPES = {"trim_whitespace", "normalize_missing"}
REVIEW_RECIPES = {"deduplicate", "map_categories", "exclude_rows"}


def repair_proposals(quality: dict[str, Any]) -> list[dict[str, Any]]:
    rules = {issue["rule"] for issue in quality.get("issues", [])}
    proposals = [
        {"recipe": "trim_whitespace", "safety": "safe", "label": "Trim surrounding whitespace", "reason": "Normalize text without changing its meaning."},
        {"recipe": "normalize_missing", "safety": "safe", "label": "Normalize missing markers", "reason": "Convert blank, N/A, null, and dash markers to a single null value."},
    ]
    if "duplicate_row" in rules: proposals.append({"recipe": "deduplicate", "safety": "review_required", "label": "Remove exact duplicate rows", "reason": "Keep the first identical source row and exclude later copies."})
    if "category_alias" in rules: proposals.append({"recipe": "map_categories", "safety": "review_required", "label": "Map category aliases", "reason": "Apply an explicit user-provided category mapping."})
    return proposals


def apply_repair(rows: list[dict[str, Any]], recipe: str, options: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if recipe not in SAFE_RECIPES | REVIEW_RECIPES: raise ValueError("Unknown or forbidden repair recipe.")
    options = options or {}; output: list[dict[str, Any]] = []; changed = 0; excluded = 0; samples = []
    excluded_rows = {int(value) for value in options.get("rows", [])}
    mappings = options.get("mapping", {})
    if recipe == "map_categories" and not isinstance(mappings, dict): raise ValueError("mapping must be an object.")
    seen: set[str] = set()
    for row_number, source in enumerate(rows, start=1):
        before = dict(source); after = dict(source)
        if recipe == "exclude_rows" and row_number in excluded_rows: excluded += 1; continue
        if recipe == "deduplicate":
            digest = json.dumps(after, sort_keys=True, default=str)
            if digest in seen: excluded += 1; continue
            seen.add(digest)
        for field, value in list(after.items()):
            if recipe == "trim_whitespace" and isinstance(value, str): after[field] = value.strip()
            elif recipe == "normalize_missing" and isinstance(value, str) and value.strip().casefold() in {"", "-", "--", "n/a", "na", "null", "none", "unknown"}: after[field] = None
            elif recipe == "map_categories" and field in mappings and isinstance(mappings[field], dict): after[field] = mappings[field].get(str(value), value)
        if after != before:
            changed += 1
            if len(samples) < 10: samples.append({"row": row_number, "before": before, "after": after})
        output.append(after)
    return output, {"recipe": recipe, "input_rows": len(rows), "output_rows": len(output), "changed_rows": changed, "excluded_rows": excluded, "samples": samples, "safety": "safe" if recipe in SAFE_RECIPES else "review_required"}
