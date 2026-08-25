"""Generate explainable, reviewable dashboard drafts from semantic contracts."""

from __future__ import annotations

from typing import Any


VARIANTS = {"recommended", "executive", "programme", "data_quality"}


def generate_dashboard(model: dict[str, Any], variant: str = "recommended") -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown dashboard variant: {variant}")
    recs = model.get("recommendations", [])
    fields = {item["name"]: item for item in model.get("fields", [])}
    selected: list[dict[str, Any]] = []
    desired = {
        "recommended": ["number", "number", "line", "bar", "map", "table"],
        "executive": ["number", "number", "number", "line", "bar"],
        "programme": ["number", "line", "bar", "map", "table"],
        "data_quality": ["number", "bar", "table"],
    }[variant]
    used: set[tuple[Any, ...]] = set()
    for view in desired:
        match = next((item for item in recs if item.get("view") == view and (view, item.get("measure"), item.get("dimension")) not in used), None)
        if not match:
            continue
        used.add((view, match.get("measure"), match.get("dimension")))
        selected.append(_widget(match, len(selected)))
    if variant == "data_quality":
        selected.insert(0, {"id": "quality_score", "kind": "quality", "view": "scorecard", "title": "Data health", "size": "small", "explanation": "Shows the governed quality score and blocking issues."})
    filters = [{"field": name, "label": fields.get(name, {}).get("label", name.replace("_", " ").title())} for name in dict.fromkeys(model.get("time_fields", []) + model.get("geography", {}).get("filter_fields", []))]
    spec = {
        "title": _title(variant), "variant": variant, "status": "draft",
        "header": {"filters": filters, "quality_score": model.get("quality", {}).get("score"), "freshness": "dataset-version"},
        "widgets": selected,
        "methods": {"schema_signature": model.get("schema_signature"), "semantic_contract_required": True, "aggregate_only": True},
    }
    spec["lint"] = lint_dashboard(spec, model)
    return spec


def lint_dashboard(spec: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    measures = {item["id"] for item in model.get("measures", [])}
    fields = {item["name"] for item in model.get("fields", [])}
    errors: list[str] = []; warnings: list[str] = []; signatures: set[tuple[Any, ...]] = set()
    for widget in spec.get("widgets", []):
        signature = (widget.get("view"), widget.get("measure"), widget.get("dimension"))
        if signature in signatures and widget.get("kind") != "quality": warnings.append(f"Duplicate analytical view: {widget.get('title')}")
        signatures.add(signature)
        if widget.get("measure") and widget["measure"] not in measures: errors.append(f"Unknown measure: {widget['measure']}")
        if widget.get("dimension") and widget["dimension"] not in fields: errors.append(f"Unknown dimension: {widget['dimension']}")
    if len(spec.get("widgets", [])) < 3: warnings.append("Dashboard has fewer than three analytical views.")
    score = max(0, 100 - len(errors) * 30 - len(warnings) * 8)
    return {"valid": not errors, "score": score, "errors": errors, "warnings": warnings}


def _widget(rec: dict[str, Any], index: int) -> dict[str, Any]:
    view = rec["view"]; measure = rec.get("measure"); dimension = rec.get("dimension")
    return {"id": f"widget_{index + 1}", "kind": "visualization", "view": view, "measure": measure, "dimension": dimension,
            "title": _widget_title(view, measure, dimension), "size": "small" if view == "number" else "wide" if view in {"line", "map", "table"} else "medium",
            "explanation": rec.get("reason", "Selected from the governed semantic contract."), "recommendation_score": rec.get("score", 0)}


def _widget_title(view: str, measure: str | None, dimension: str | None) -> str:
    metric = (measure or "records").replace("_", " ").title()
    return f"{metric} over time" if view == "line" else f"{metric} by {(dimension or 'category').replace('_', ' ').title()}" if view in {"bar", "map"} else metric


def _title(variant: str) -> str:
    return {"recommended": "Recommended overview", "executive": "Executive overview", "programme": "Programme performance", "data_quality": "Data quality review"}[variant]
