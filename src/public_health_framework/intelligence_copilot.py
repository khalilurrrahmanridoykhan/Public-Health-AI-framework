"""Governed knowledge packs and a constrained dashboard copilot."""

from __future__ import annotations

import re
from typing import Any


KNOWLEDGE_PACKS = [
    {"id": "routine", "version": "1.0", "name": "Routine service delivery", "roles": ["time", "geography", "measure"], "views": ["number", "line", "bar", "map"]},
    {"id": "maternal_child", "version": "1.0", "name": "Maternal and child health", "roles": ["time", "geography", "measure"], "views": ["number", "line", "bar"]},
    {"id": "immunization", "version": "1.0", "name": "Immunization programme", "roles": ["time", "geography", "measure"], "views": ["number", "line", "map"]},
    {"id": "surveillance", "version": "1.0", "name": "Disease surveillance", "roles": ["time", "geography", "measure"], "views": ["number", "line", "map", "table"]},
    {"id": "malaria", "version": "1.0", "name": "Malaria programme", "roles": ["time", "geography", "measure"], "views": ["number", "line", "bar", "map"]},
    {"id": "nutrition", "version": "1.0", "name": "Nutrition monitoring", "roles": ["time", "measure", "dimension"], "views": ["number", "line", "bar"]},
    {"id": "supplies", "version": "1.0", "name": "Commodities and stock", "roles": ["time", "geography", "measure"], "views": ["number", "line", "bar", "table"]},
    {"id": "data_quality", "version": "1.0", "name": "Data quality review", "roles": [], "views": ["scorecard", "bar", "table"]},
]

ALLOWED_ACTIONS = {"generate_dashboard", "add_visualization", "add_filter", "change_variant", "explain_recommendation"}
UNSAFE = re.compile(r"(?:<script|javascript:|\bdrop\s+table\b|\bdelete\s+from\b|\bexec(?:ute)?\b|ignore (?:all|previous) instructions)", re.I)


def propose_change(prompt: str, semantic: dict[str, Any], dashboard: dict[str, Any] | None = None) -> dict[str, Any]:
    prompt = prompt.strip()
    if not prompt: raise ValueError("Prompt is required.")
    if len(prompt) > 1000 or UNSAFE.search(prompt): raise ValueError("The request contains an unsafe or unsupported instruction.")
    lower = prompt.lower(); action = "explain_recommendation"; change: dict[str, Any] = {}
    if "executive" in lower: action = "change_variant"; change = {"variant": "executive"}
    elif "quality" in lower: action = "change_variant"; change = {"variant": "data_quality"}
    elif "programme" in lower or "program" in lower: action = "change_variant"; change = {"variant": "programme"}
    elif "filter" in lower:
        action = "add_filter"; candidates = semantic.get("time_fields", []) + semantic.get("geography", {}).get("filter_fields", [])
        if not candidates: raise ValueError("No governed filter field is available.")
        change = {"field": candidates[0]}
    elif any(word in lower for word in ("chart", "map", "visual", "kpi")):
        requested = "map" if "map" in lower else "line" if "trend" in lower else "number" if "kpi" in lower else "bar"
        rec = next((item for item in semantic.get("recommendations", []) if item.get("view") == requested), None)
        if not rec: raise ValueError(f"The semantic contract does not support a {requested} visualization.")
        action = "add_visualization"; change = {key: rec.get(key) for key in ("view", "measure", "dimension", "reason")}
    elif "dashboard" in lower: action = "generate_dashboard"; change = {"variant": "recommended"}
    if action not in ALLOWED_ACTIONS: raise ValueError("Unsupported action.")
    return {"action": action, "status": "proposal", "requires_approval": True, "change": change,
            "explanation": "This proposal is constrained to the approved semantic contract and will not change data or dashboards until a person approves it.",
            "current_dashboard_id": (dashboard or {}).get("id")}


def match_knowledge_packs(semantic: dict[str, Any]) -> list[dict[str, Any]]:
    roles = {field.get("role") for field in semantic.get("fields", [])}
    result = []
    for pack in KNOWLEDGE_PACKS:
        missing = sorted(set(pack["roles"]) - roles)
        result.append({**pack, "compatible": not missing, "missing_roles": missing, "score": max(0, 100 - len(missing) * 30)})
    return sorted(result, key=lambda item: (-item["score"], item["name"]))
