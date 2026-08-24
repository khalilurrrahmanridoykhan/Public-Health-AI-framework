"""Privacy-aware, evidence-grounded assistance for PHFrame projects."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen

from .config import DatasetSchema


DIRECT_IDENTIFIER_TYPES = {"identifier"}


@dataclass(frozen=True)
class PrivacyResult:
    records: list[dict[str, Any]]
    removed_fields: tuple[str, ...]
    transformed_fields: tuple[str, ...]
    source_rows: int


def deidentify_records(dataset: DatasetSchema, records: list[dict[str, Any]]) -> PrivacyResult:
    """Remove protected/direct identifiers and generalize person-level dates and ages."""
    removed = {
        name for name, field in dataset.fields.items()
        if field.protected or field.type in DIRECT_IDENTIFIER_TYPES
    }
    transformed = {
        name for name, field in dataset.fields.items()
        if name not in removed and field.type in {"date", "datetime", "age"}
    }
    clean = []
    for record in records:
        item: dict[str, Any] = {}
        for name, field in dataset.fields.items():
            if name in removed or name not in record:
                continue
            value = record.get(name)
            if value is None:
                item[name] = None
            elif field.type in {"date", "datetime"}:
                item[name] = str(value)[:4]
            elif field.type == "age":
                age = int(value)
                item[name] = "90+" if age > 89 else f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
            else:
                item[name] = value
        clean.append(item)
    return PrivacyResult(clean, tuple(sorted(removed)), tuple(sorted(transformed)), len(records))


def evidence_digest(evidence: list[dict[str, Any]]) -> str:
    return sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def local_summary(title: str, evidence: list[dict[str, Any]], purpose: str = "") -> str:
    """Produce a conservative narrative whose every factual statement cites evidence."""
    lines = [f"## {title}", "", "AI-assisted draft — requires human review before use."]
    if purpose:
        lines.extend(["", f"Purpose: {purpose.strip()}"])
    lines.extend(["", "### Evidence-backed observations"])
    for index, item in enumerate(evidence, 1):
        kind = item.get("kind")
        label = item.get("label", item.get("name", "Evidence"))
        if kind == "indicator":
            value = "no data" if item.get("value") is None else f"{item['value']:g}"
            lines.append(f"- {label}: **{value}** [{index}].")
        elif kind == "dimension":
            values = item.get("values", [])[:5]
            detail = ", ".join(f"{entry['value']} ({entry['count']})" for entry in values) or "no grouped data"
            lines.append(f"- {label}: {detail} [{index}].")
        elif kind == "quality":
            score = "not available" if item.get("score") is None else f"{item['score']:.1f}%"
            lines.append(f"- Data quality — {label}: {score}; {item.get('violations', 0)} violation(s) [{index}].")
        elif kind == "threshold":
            lines.append(f"- Alert — {label}: {item.get('status', 'unknown')} (observed {item.get('actual')}, threshold {item.get('threshold')}) [{index}].")
    lines.extend(["", "### Limitations", "- This draft summarizes configured aggregate evidence only. It is not a diagnosis, forecast, or clinical recommendation.", "- Verify completeness, context, denominators, reporting delays, and data-quality issues before approval.", "", "### Evidence register"])
    for index, item in enumerate(evidence, 1):
        lines.append(f"[{index}] {item.get('endpoint', 'PHFrame aggregate')} — {item.get('label', item.get('name', 'Evidence'))}")
    return "\n".join(lines)


def generate_summary(title: str, evidence: list[dict[str, Any]], purpose: str, settings: dict[str, Any]) -> tuple[str, str, str]:
    provider = settings.get("ai_provider", "local")
    model = settings.get("ai_model", "phframe-evidence-v1")
    if provider == "local":
        return local_summary(title, evidence, purpose), provider, model
    if not settings.get("allow_external_ai"):
        raise ValueError("External AI is disabled. Enable it explicitly in Settings after completing your privacy review.")
    endpoint = str(settings.get("ai_endpoint", "")).strip()
    key_env = str(settings.get("ai_api_key_env", "")).strip()
    if not endpoint.startswith("https://") or not key_env or not os.environ.get(key_env):
        raise ValueError("External AI requires an HTTPS endpoint and a configured API-key environment variable.")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Write a cautious public-health summary using only the supplied aggregate evidence. Cite every factual claim with its [E#] evidence ID. Do not diagnose, predict, or invent facts."},
            {"role": "user", "content": json.dumps({"title": title, "purpose": purpose, "evidence": [{"id": f"E{i}", **item} for i, item in enumerate(evidence, 1)]})},
        ],
        "temperature": 0,
    }
    request = Request(endpoint, data=json.dumps(payload).encode(), headers={"authorization": f"Bearer {os.environ[key_env]}", "content-type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:  # nosec: endpoint is administrator-configured HTTPS
        result = json.loads(response.read())
    try:
        content = str(result["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("External AI returned an unsupported response.") from error
    citations = {int(value) for value in re.findall(r"\[E(\d+)\]", content)}
    if not citations or any(value < 1 or value > len(evidence) for value in citations):
        raise ValueError("External AI output was rejected because it did not contain valid evidence citations.")
    return content, provider, model
