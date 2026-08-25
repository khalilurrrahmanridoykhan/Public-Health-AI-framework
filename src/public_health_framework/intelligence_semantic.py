"""Compile governed semantic contracts and compatible visualization choices."""

from __future__ import annotations

from typing import Any


def compile_semantic_model(profile: dict[str, Any], quality: dict[str, Any] | None = None, geography: dict[str, Any] | None = None) -> dict[str, Any]:
    quality = quality or {}; geography = (geography or {}).get("model", geography or {})
    fields = []
    for column in profile["columns"]:
        role = _role(column)
        fields.append({"name": column["name"], "label": column["name"].replace("_", " ").title(), "storage_type": column["storage_type"], "semantic_type": column["semantic_type"], "role": role, "confidence": column["confidence"], "cardinality": column["distinct"], "missing_percent": column["missing_percent"]})
    measures = []
    for field in fields:
        if field["role"] == "measure":
            measures.extend([
                {"id": f"sum_{field['name']}", "label": f"Total {field['label']}", "operation": "sum", "field": field["name"], "format": "number"},
                {"id": f"average_{field['name']}", "label": f"Average {field['label']}", "operation": "average", "field": field["name"], "format": "decimal"},
            ])
    measures.insert(0, {"id": "record_count", "label": "Record count", "operation": "count", "field": None, "format": "integer"})
    recommendations = recommend_visualizations(fields, measures, geography, quality)
    return {"schema_signature": profile["schema_signature"], "fields": fields, "measures": measures, "time_fields": [item["name"] for item in fields if item["role"] == "time"], "dimension_fields": [item["name"] for item in fields if item["role"] in {"dimension", "geography"}], "geography": geography, "quality": {key: quality.get(key) for key in ("score", "readiness", "blocker_count")}, "recommendations": recommendations}


def recommend_visualizations(fields: list[dict[str, Any]], measures: list[dict[str, Any]], geography: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    # Validated geography labels are also useful comparison dimensions.  Keeping
    # them eligible here avoids forcing every location analysis onto a map.
    dimensions = [item for item in fields if item["role"] in {"dimension", "geography"} and item["cardinality"] <= 30]
    times = [item for item in fields if item["role"] == "time"]
    recommendations = []
    for measure in measures[:8]:
        recommendations.append(_rec("number", measure, None, 96, "A governed aggregate is suitable for a KPI card."))
        if times: recommendations.append(_rec("line", measure, times[0], 94, "A time field and aggregate measure support trend analysis."))
        if dimensions: recommendations.append(_rec("bar", measure, dimensions[0], 90, "A low-cardinality category supports readable comparison."))
        if dimensions and dimensions[0]["cardinality"] <= 6: recommendations.append(_rec("donut", measure, dimensions[0], 72, "Few categories permit a part-to-whole view; bar remains preferred."))
        if geography.get("map_ready") and geography.get("filter_fields"): recommendations.append(_rec("map", measure, {"name": geography["filter_fields"][-1]}, 88, "A validated geographic field supports spatial comparison."))
    recommendations.append({"view": "table", "measure": None, "dimension": None, "score": 82, "reason": "A detail table preserves inspectability.", "compatible": True})
    if quality.get("readiness") == "blocked":
        for item in recommendations:
            if item["view"] != "table": item["score"] = max(0, item["score"] - 25); item["warning"] = "Quality blockers must be resolved before publication."
    return sorted(recommendations, key=lambda item: item["score"], reverse=True)


def _role(column: dict[str, Any]) -> str:
    semantic = column["semantic_type"]
    if semantic in {"date", "datetime", "reporting_period"}: return "time"
    if semantic in {"location", "organisation_unit", "latitude", "longitude", "geometry"}: return "geography"
    if semantic == "measure" or column["storage_type"] in {"integer", "number"}: return "measure"
    if semantic == "identifier": return "identifier"
    return "dimension" if column["distinct"] <= 100 else "attribute"


def _rec(view: str, measure: dict[str, Any], dimension: dict[str, Any] | None, score: int, reason: str) -> dict[str, Any]:
    return {"view": view, "measure": measure["id"], "dimension": dimension["name"] if dimension else None, "score": score, "reason": reason, "compatible": True}
