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


def enrich_trend(label: str, points: list[dict[str, Any]], endpoint: str) -> dict[str, Any]:
    values = [float(point["value"]) for point in points]
    first, latest = (values[0], values[-1]) if values else (None, None)
    change = latest - first if values else None
    percent = (change / first * 100) if values and first else None
    direction = "stable"
    if change is not None and change > 0: direction = "increasing"
    if change is not None and change < 0: direction = "decreasing"
    anomaly = None
    if len(values) >= 4:
        baseline = values[:-1]
        mean = sum(baseline) / len(baseline)
        variance = sum((value - mean) ** 2 for value in baseline) / len(baseline)
        deviation = variance ** .5
        score = (latest - mean) / deviation if deviation else 0
        if abs(score) >= 2:
            anomaly = {"score": round(score, 2), "direction": "above" if score > 0 else "below", "baseline_mean": round(mean, 2)}
    return {"kind": "trend", "name": label.lower().replace(" ", "_"), "label": label, "points": points, "first": first, "latest": latest, "change": change, "percent_change": percent, "direction": direction, "anomaly": anomaly, "endpoint": endpoint}


def answer_question(question: str, evidence: list[dict[str, Any]], previous_evidence: list[str] | None = None) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Answer an analyst question using only computed evidence and explicit uncertainty."""
    query = question.lower().strip()
    if not query:
        raise ValueError("question is required.")
    stop = {"what", "which", "where", "when", "show", "tell", "about", "give", "with", "from", "this", "that", "have", "does", "data", "please"}
    tokens = {token for token in re.findall(r"[a-z0-9_]+", query) if len(token) > 2 and token not in stop}
    intent = "overview"
    if any(word in query for word in ("trend", "increase", "decrease", "change", "over time", "rising", "falling")): intent = "trend"
    if any(word in query for word in ("unusual", "anomal", "spike", "outlier", "unexpected")): intent = "anomaly"
    if any(word in query for word in ("compare", "versus", " vs ", "difference", "highest", "lowest", "location", "district", "country")): intent = "comparison"
    if any(word in query for word in ("quality", "missing", "invalid", "complete")): intent = "quality"
    if any(word in query for word in ("alert", "threshold", "warning", "critical")): intent = "alert"
    if any(word in query for word in ("why", "cause", "reason", "explain")): intent = "explanation"
    kind_priority = {
        "trend": {"trend"}, "anomaly": {"trend"}, "comparison": {"dimension"},
        "quality": {"quality"}, "alert": {"threshold"}, "explanation": {"trend", "dimension", "quality", "threshold"},
    }.get(intent, {"indicator", "trend", "dimension", "quality", "threshold"})
    scored = []
    for item in evidence:
        searchable = " ".join(str(item.get(key, "")) for key in ("name", "label", "dataset", "field")).lower()
        score = (4 if item.get("kind") in kind_priority else 0) + sum(2 for token in tokens if token in searchable)
        if item.get("kind") == "dimension" and any(str(entry.get("value", "")).lower() in query for entry in item.get("values", [])): score += 5
        if item.get("name") in (previous_evidence or []): score += 1
        scored.append((score, item))
    selected = [item for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True) if score > 0][:6]
    if not selected: selected = evidence[:6]
    lines = ["### Analyst answer"]
    if intent == "explanation":
        lines.append("The available aggregates can show **what changed**, but they cannot establish a cause. The observations below identify signals to investigate:")
    for index, item in enumerate(selected, 1):
        kind, label = item.get("kind"), item.get("label", item.get("name", "Evidence"))
        if kind == "indicator":
            value = "no data" if item.get("value") is None else f"{item['value']:g}"
            lines.append(f"- **{label}: {value}.** This is the configured {item.get('operation', 'aggregate')} result [E{index}].")
        elif kind == "dimension":
            ranked = sorted(item.get("values", []), key=lambda entry: entry["count"], reverse=True)
            if ranked:
                top = ranked[0]; runner = ranked[1] if len(ranked) > 1 else None
                comparison = f", followed by {runner['value']} ({runner['count']})" if runner else ""
                lines.append(f"- **{label}:** {top['value']} has the highest count ({top['count']}){comparison} [E{index}].")
            else: lines.append(f"- **{label}:** no grouped observations are available [E{index}].")
        elif kind == "trend":
            percent = "not calculable" if item.get("percent_change") is None else f"{item['percent_change']:+.1f}%"
            lines.append(f"- **{label} is {item['direction']}:** {item.get('first')} to {item.get('latest')} ({percent}) across {len(item.get('points', []))} reported points [E{index}].")
            if item.get("anomaly"):
                anomaly = item["anomaly"]
                lines.append(f"- The latest value is unusually {anomaly['direction']} the earlier baseline (z-score {anomaly['score']}, baseline mean {anomaly['baseline_mean']}) [E{index}].")
        elif kind == "quality":
            score = "not available" if item.get("score") is None else f"{item['score']:.1f}%"
            lines.append(f"- **{label}:** quality score {score}, with {item.get('violations', 0)} violation(s) among {item.get('total', 0)} records [E{index}].")
        elif kind == "threshold":
            lines.append(f"- **{label}: {item.get('status')}.** Observed {item.get('actual')} against threshold {item.get('threshold')} [E{index}].")
    if intent in {"explanation", "anomaly", "trend", "alert"}:
        lines.extend(["", "### Suggested investigation", "1. Confirm reporting completeness and recent data-quality violations.", "2. Compare the signal by location and reporting unit.", "3. Check reporting delays, definition changes, duplicate records, and connector/import history.", "4. Ask a subject-matter expert to interpret operational or epidemiological context."])
    lines.extend(["", "### Safety note", "This answer uses aggregate project evidence only. It does not establish causality, predict future events, or provide diagnosis or clinical advice.", "", "### Evidence"])
    for index, item in enumerate(selected, 1): lines.append(f"[E{index}] {item.get('label', item.get('name'))} — {item.get('endpoint')}")
    meta = {"intent": intent, "evidence_names": [item.get("name") for item in selected], "question_tokens": sorted(tokens)}
    return "\n".join(lines), selected, meta


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
