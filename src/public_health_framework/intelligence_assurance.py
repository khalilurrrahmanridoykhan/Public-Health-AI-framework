"""Detect dataset drift and decide whether dashboards may refresh safely."""

from __future__ import annotations

from typing import Any


def assess_drift(current: dict[str, Any], previous: dict[str, Any] | None, current_quality: dict[str, Any] | None = None, previous_quality: dict[str, Any] | None = None, dashboards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not previous:
        return {"severity": "baseline", "schema_changed": False, "changes": [], "affected_dashboards": [], "refresh_action": "approval_required", "publish_allowed": False}
    cur = {item["name"]: item for item in current["profile"]["columns"]}; old = {item["name"]: item for item in previous["profile"]["columns"]}
    changes: list[dict[str, Any]] = []
    for name in sorted(cur.keys() - old.keys()): changes.append({"kind": "column_added", "field": name, "severity": "warning"})
    for name in sorted(old.keys() - cur.keys()): changes.append({"kind": "column_removed", "field": name, "severity": "blocking"})
    for name in sorted(cur.keys() & old.keys()):
        if cur[name]["storage_type"] != old[name]["storage_type"]: changes.append({"kind": "storage_type_changed", "field": name, "from": old[name]["storage_type"], "to": cur[name]["storage_type"], "severity": "blocking"})
        elif cur[name]["semantic_type"] != old[name]["semantic_type"]: changes.append({"kind": "semantic_type_changed", "field": name, "from": old[name]["semantic_type"], "to": cur[name]["semantic_type"], "severity": "warning"})
    old_rows = max(1, int(previous.get("row_count", 0))); ratio = abs(int(current.get("row_count", 0)) - old_rows) / old_rows
    if ratio >= .5: changes.append({"kind": "row_volume_changed", "percent": round(ratio * 100, 1), "severity": "warning"})
    quality_delta = round(float((current_quality or {}).get("score", 0)) - float((previous_quality or {}).get("score", 0)), 1)
    if quality_delta <= -15: changes.append({"kind": "quality_regressed", "delta": quality_delta, "severity": "blocking"})
    severity = "blocking" if any(item["severity"] == "blocking" for item in changes) else "warning" if changes else "none"
    impacted = [{"id": item["id"], "variant": item["variant"], "reason": "The source contract changed."} for item in (dashboards or [])] if changes else []
    return {"severity": severity, "schema_changed": current.get("schema_signature") != previous.get("schema_signature"), "changes": changes,
            "quality_delta": quality_delta, "affected_dashboards": impacted,
            "refresh_action": "refresh_in_place" if severity == "none" else "approval_required", "publish_allowed": severity in {"none", "warning"}}


def evaluate_assurance(report: dict[str, Any]) -> dict[str, Any]:
    checks = {"blocks_structural_breaks": report["severity"] == "blocking" and report["refresh_action"] == "approval_required",
              "lists_impacted_dashboards": not report["changes"] or bool(report["affected_dashboards"]),
              "uses_explicit_publish_policy": isinstance(report.get("publish_allowed"), bool)}
    return {"passed": all(checks.values()), "checks": checks}
