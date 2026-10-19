import json
from pathlib import Path
import re
from typing import Any

import pytest
from starlette.testclient import TestClient

from public_health_framework import application
from public_health_framework.application import PHFrame
from public_health_framework.contract import framework_contract
from public_health_framework.http_reference import OPERATIONS, build_markdown, build_openapi, openapi_path, operation_keys
from public_health_framework.project import create_project
from public_health_framework.ui import asset_bytes

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
REGENERATE = "python -m public_health_framework.http_reference --write docs"
SPEC = build_openapi()


def resolve(schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = SPEC["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def errors(value: Any, schema: dict[str, Any], where: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by the reference."""
    schema = resolve(schema)
    found: list[str] = []
    if "allOf" in schema:
        for part in schema["allOf"]:
            found += errors(value, part, where)
    if "anyOf" in schema and all(errors(value, option, where) for option in schema["anyOf"]):
        found.append(f"{where}: matches no anyOf option")
    if "oneOf" in schema and sum(not errors(value, option, where) for option in schema["oneOf"]) != 1:
        found.append(f"{where}: must match exactly one oneOf option")
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        checks = {
            "object": lambda item: isinstance(item, dict), "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str), "boolean": lambda item: isinstance(item, bool),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
            "null": lambda item: item is None,
        }
        if not any(checks[kind](value) for kind in kinds):
            return found + [f"{where}: expected {'/'.join(kinds)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{where}: {value!r} not in {schema['enum']}")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                found.append(f"{where}: missing required field {name!r}")
        properties = schema.get("properties", {})
        for name, item in value.items():
            if name in properties:
                found += errors(item, properties[name], f"{where}.{name}")
            elif isinstance(schema.get("additionalProperties"), dict):
                found += errors(item, schema["additionalProperties"], f"{where}.{name}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            found += errors(item, schema["items"], f"{where}[{index}]")
    return found


def find_operation(method: str, url: str) -> str:
    path = url.split("?", 1)[0]
    matches = []
    for item in OPERATIONS:
        pattern = re.sub(r"{[^}:]+:int}", r"[0-9]+", item.path)
        pattern = re.sub(r"{[^}]+}", r"[^/]+", pattern)
        if item.method == method and re.fullmatch(pattern, path):
            matches.append(item)
    # Starlette matches routes in order; literal routes such as /api/indicators win over /api/{dataset}.
    matches.sort(key=lambda item: item.path.count("{"))
    assert matches, f"{method} {path} is not documented"
    return f"{method} {matches[0].path}"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("PHFRAME_RATE_LIMIT", "10000")
    for name in ("PHFRAME_DHIS2_CLIENT_ID", "PHFRAME_DHIS2_CLIENT_SECRET", "PHFRAME_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(application, "_VENDOR_CACHE", {
        "leaflet.css": b".leaflet{}", "leaflet.js": b"var L={};",
        "gridstack.css": b".grid-stack{}", "gridstack.js": b"var GridStack={};",
        "chart.js": b"var Chart={};",
    })
    root = create_project("Reference", tmp_path / "reference")
    return TestClient(PHFrame.from_file(str(root / "phframe.yaml")), follow_redirects=False)


def test_every_contract_route_is_documented():
    contract = framework_contract()
    routes = {f"{method} {route['path']}" for route in contract["http"] for method in route["methods"]}
    assert routes - operation_keys() == set(), f"Document these routes in http_reference.py: {sorted(routes - operation_keys())}"
    assert operation_keys() - routes == set(), f"Documented routes that the application does not serve: {sorted(operation_keys() - routes)}"


def test_reference_documents_are_current():
    assert json.loads((DOCS / "openapi.json").read_text(encoding="utf-8")) == SPEC, f"docs/openapi.json is stale; run `{REGENERATE}`."
    assert (DOCS / "http-api.md").read_text(encoding="utf-8") == build_markdown(SPEC), f"docs/http-api.md is stale; run `{REGENERATE}`."


def test_schema_references_resolve():
    text = json.dumps(SPEC)
    for name in set(re.findall(r'"#/components/schemas/([A-Za-z0-9]+)"', text)):
        assert name in SPEC["components"]["schemas"], name
    ids = [operation["operationId"] for methods in SPEC["paths"].values() for operation in methods.values()]
    assert len(ids) == len(set(ids)), "operationId values must be unique"


def test_validator_rejects_mismatches():
    record = {"$ref": "#/components/schemas/Record"}
    assert errors({"id": 1, "created_at": "t", "updated_at": "t", "cases": 3}, record) == []
    assert sorted(errors({"id": "1", "created_at": "t"}, record)) == ["$.id: expected integer, got str", "$: missing required field 'updated_at'"]


def test_live_responses_match_the_reference(client: TestClient):
    app: PHFrame = client.app
    boundary_dir = app.site_settings.boundary_dir
    boundary_dir.mkdir(parents=True, exist_ok=True)
    (boundary_dir / "countries.json").write_text(json.dumps([{"name": "Bangladesh", "iso3": "BGD"}]), encoding="utf-8")
    (boundary_dir / "BGD-ADM1.json").write_text(json.dumps({
        "id": "BGD-ADM1", "country": "Bangladesh", "iso3": "BGD", "level": "ADM1", "year": 2020, "source": "geoBoundaries",
        "license": "CC BY 4.0", "feature_count": 0, "geojson": {"type": "FeatureCollection", "features": []},
    }), encoding="utf-8")
    csv = (EXAMPLES / "case_reports.csv").read_bytes()
    record = {"case_id": "REF-1", "disease": "Malaria", "status": "confirmed", "report_date": "2026-07-20", "district": "Dhaka", "cases": 3, "population": 1000}
    connector = {"name": "reference_feed", "type": "api", "dataset": "case_reports", "base_url": "http://127.0.0.1:9", "resource": "cases",
                 "mapping": {"cases": "cases"}, "timeout": 1}
    publication = {"dashboard_id": "configured-main"}
    calls: list[tuple[str, str, dict[str, Any]]] = [
        ("GET", "/health", {}), ("GET", "/ready", {}), ("GET", "/api", {}), ("GET", "/api/openapi.json", {}),
        ("GET", "/", {}), ("GET", "/app", {}), ("GET", "/login", {}),
        ("GET", "/assets/phframe.css", {}), ("GET", "/assets/phframe.js", {}), ("GET", "/assets/leaflet.css", {}),
        ("GET", "/assets/leaflet.js", {}), ("GET", "/assets/gridstack.css", {}), ("GET", "/assets/gridstack.js", {}),
        ("GET", "/assets/chart.js", {}), ("GET", "/assets/phframe-logo.png", {}), ("GET", "/assets/project/logo", {}),
        ("POST", "/api/settings/assets/logo?filename=logo.png", {"content": asset_bytes("phframe-logo.png")}),
        ("POST", "/api/settings/assets/logo?filename=logo.txt", {"content": b"x"}),
        ("GET", "/assets/project/logo", {}),
        ("GET", "/api/auth/status", {}), ("POST", "/api/auth/login", {"json": {"username": "nobody", "password": "wrong"}}),
        ("POST", "/api/auth/login", {"content": b"not json"}),
        ("GET", "/api/settings", {}), ("PUT", "/api/settings", {"json": {"brand_name": "Reference", "username": "admin", "password": "reference-pass-1"}}),
        ("POST", "/api/auth/login", {"json": {"username": "admin", "password": "reference-pass-1"}}), ("POST", "/api/auth/logout", {}),
        ("PUT", "/api/settings", {"json": {"access_mode": "secret"}}),
        ("GET", "/api/boundaries", {}), ("POST", "/api/boundaries", {"json": {"iso3": "B", "level": "ADM9"}}),
        ("GET", "/api/boundaries/countries", {}), ("GET", "/api/boundaries/BGD-ADM1", {}), ("GET", "/api/boundaries/missing", {}),
        # Records
        ("POST", "/api/case_reports", {"json": record}), ("POST", "/api/case_reports", {"json": {"cases": "many"}}),
        ("POST", "/api/missing", {"json": record}), ("GET", "/api/case_reports?limit=5", {}), ("GET", "/api/case_reports?limit=x", {}),
        ("GET", "/api/case_reports?unknown=1", {}), ("GET", "/api/missing", {}),
        ("GET", "/api/case_reports/1", {}), ("GET", "/api/case_reports/999", {}),
        ("PUT", "/api/case_reports/1", {"json": {**record, "cases": 5}}), ("PATCH", "/api/case_reports/1", {"json": {"cases": 6}}),
        ("PATCH", "/api/case_reports/999", {"json": {"cases": 6}}), ("PATCH", "/api/case_reports/1", {"json": {"cases": "six"}}),
        ("POST", "/api/project/datasets/case_reports/fields", {"json": {"name": "notes", "type": "string"}}),
        ("POST", "/api/project/datasets/case_reports/fields", {"json": {"name": "Bad Name"}}),
        ("POST", "/api/project/datasets/missing/fields", {"json": {"name": "notes"}}),
        # Imports and staging
        ("POST", "/api/browser-import/case_reports/preview?filename=cases.csv", {"content": csv}),
        ("POST", "/api/browser-import/case_reports/preview", {"content": csv}),
        ("POST", "/api/browser-import/case_reports?filename=cases.csv", {"content": csv}),
        ("POST", "/api/browser-import/case_reports?filename=bad.csv", {"content": b"case_id,cases\nX,many\n"}),
        ("POST", "/api/browser-import/case_reports?version_id=1&dry_run=true", {}),
        ("GET", "/api/import-example/case_reports", {}), ("GET", "/api/import-example/case_reports?format=json", {}),
        ("GET", "/api/import-example/case_reports?format=xml", {}), ("GET", "/api/import-example/case_reports?format=pdf", {}),
        ("GET", "/api/import-example/missing", {}),
        ("PUT", "/api/import-mappings/district_map", {"json": {"dataset": "case_reports", "mapping": {"District": "district"}}}),
        ("PUT", "/api/import-mappings/district_map", {"json": {"dataset": "case_reports", "mapping": {}}}),
        ("GET", "/api/import-mappings", {}), ("GET", "/api/imports", {}), ("GET", "/api/imports?limit=x", {}),
        ("GET", "/api/imports/1/errors", {}), ("GET", "/api/imports/999/errors", {}),
        ("GET", "/api/staging", {}), ("GET", "/api/staging?limit=x", {}), ("GET", "/api/staging?dataset=missing", {}),
        ("GET", "/api/staging/1", {}), ("GET", "/api/staging/999", {}),
        ("GET", "/api/staging/1/rows?limit=2", {}), ("GET", "/api/staging/1/rows?limit=x", {}), ("GET", "/api/staging/999/rows", {}),
        ("GET", "/api/staging/1/quality", {}), ("POST", "/api/staging/1/quality", {}), ("POST", "/api/staging/999/quality", {}),
        ("GET", "/api/staging/1/repairs", {}), ("GET", "/api/staging/999/repairs", {}),
        ("POST", "/api/staging/1/repairs", {"json": {"recipe": "trim_whitespace"}}),
        ("POST", "/api/staging/1/repairs", {"json": {"recipe": "trim_whitespace", "preview": False, "reason": "Reference"}}),
        ("POST", "/api/staging/1/repairs", {"json": {"recipe": "unknown_recipe"}}),
        ("GET", "/api/transformations", {}), ("GET", "/api/transformations?limit=x", {}),
        ("GET", "/api/staging/1/geography", {}), ("POST", "/api/staging/1/geography", {}), ("GET", "/api/staging/1/geography", {}),
        ("POST", "/api/staging/999/geography", {}),
        ("GET", "/api/staging/1/semantic", {}), ("POST", "/api/staging/1/dashboards", {}),
        ("POST", "/api/staging/1/assistant", {"json": {"prompt": "x"}}),
        ("POST", "/api/staging/1/semantic", {}), ("GET", "/api/staging/1/semantic", {}), ("POST", "/api/staging/999/semantic", {}),
        ("PATCH", "/api/staging/1/semantic", {"json": {"model_id": 1}}), ("PATCH", "/api/staging/1/semantic", {"json": {"model_id": "x"}}),
        ("PATCH", "/api/staging/1/semantic", {"json": {"model_id": 1}}),
        ("POST", "/api/staging/1/dashboards", {"json": {"variant": "recommended"}}), ("POST", "/api/staging/1/dashboards", {"json": {"variant": "nope"}}),
        ("GET", "/api/staging/1/dashboards", {}),
        ("PATCH", "/api/staging/1/dashboards/1", {}), ("PATCH", "/api/staging/1/dashboards/999", {}),
        ("GET", "/api/intelligence/knowledge-packs", {}), ("GET", "/api/intelligence/knowledge-packs?version_id=1", {}),
        ("GET", "/api/intelligence/knowledge-packs?version_id=999", {}),
        ("POST", "/api/staging/1/assistant", {"json": {"prompt": "Show cases by district"}}),
        ("GET", "/api/staging/1/assurance", {}), ("POST", "/api/staging/1/assurance", {}), ("POST", "/api/staging/2/assurance", {}),
        ("GET", "/api/staging/1/assurance", {}), ("POST", "/api/staging/999/assurance", {}),
        ("PATCH", "/api/staging/1", {"json": {"status": "approved"}}), ("PATCH", "/api/staging/1", {"json": {"status": "not-a-status"}}), ("PATCH", "/api/staging/999", {"json": {"status": "approved"}}),
        # Analytics
        ("GET", "/api/indicators", {}), ("GET", "/api/indicators/total_cases", {}), ("GET", "/api/indicators/total_cases?period=last_7_days", {}),
        ("GET", "/api/indicators/total_cases?period=bogus", {}), ("GET", "/api/indicators/missing", {}),
        ("GET", "/api/data-quality", {}), ("GET", "/api/data-quality/cases_nonnegative", {}), ("GET", "/api/data-quality/missing", {}),
        ("GET", "/api/filters", {}), ("GET", "/api/dimensions", {}), ("GET", "/api/dimensions/cases_by_district", {}),
        ("GET", "/api/dimensions/cases_by_district?filter=missing", {}), ("GET", "/api/dimensions/missing", {}),
        ("GET", "/api/thresholds", {}), ("GET", "/api/thresholds?period=bogus", {}), ("GET", "/api/thresholds/high_weekly_case_count", {}),
        ("GET", "/api/thresholds/high_weekly_case_count?period=bogus", {}), ("GET", "/api/thresholds/missing", {}),
        ("GET", "/api/organisation-units", {}), ("GET", "/api/organisation-units/example_site", {}), ("GET", "/api/organisation-units/missing", {}),
        ("GET", "/api/dashboards/main", {}), ("GET", "/api/dashboards/missing", {}),
        ("GET", "/api/epi-curve/case_reports?date_field=report_date&value_field=cases", {}), ("GET", "/api/epi-curve/case_reports?date_field=nope", {}),
        ("GET", "/api/epi-curve/missing", {}),
        ("GET", "/api/visualize/case_reports?field=district", {}), ("GET", "/api/visualize/case_reports?field=cases&operation=average", {}),
        ("GET", "/api/visualize/case_reports?field=nope", {}), ("GET", "/api/visualize/missing?field=x", {}),
        ("GET", "/api/geospatial/case_reports?latitude=cases&longitude=population", {}), ("GET", "/api/geospatial/case_reports?latitude=district&longitude=x", {}),
        ("GET", "/api/geospatial/missing", {}),
        # Connectors
        ("POST", "/api/connectors", {"json": connector}), ("POST", "/api/connectors", {"json": {**connector, "type": "ftp"}}),
        ("GET", "/api/connectors", {}), ("POST", "/api/connectors/reference_feed/sync?dry_run=true", {}),
        ("POST", "/api/connectors/missing/sync", {}), ("GET", "/api/syncs", {}), ("GET", "/api/syncs?limit=x", {}),
        ("DELETE", "/api/connectors/reference_feed", {}), ("DELETE", "/api/connectors/reference_feed", {}),
        # Integrations
        ("GET", "/api/integrations/cloudflare/status", {}), ("GET", "/api/integrations/cloudflare/connect", {}),
        ("GET", "/api/integrations/cloudflare/callback?error=access_denied", {}), ("GET", "/api/integrations/cloudflare/callback?code=x&state=y", {}),
        ("GET", "/api/integrations/cloudflare/broker/callback?broker_code=x&state=y", {}),
        ("PUT", "/api/integrations/cloudflare/account", {"json": {"account_id": "unknown"}}), ("POST", "/api/integrations/cloudflare/disconnect", {}),
        ("GET", "/api/integrations/dhis2/status", {}), ("GET", "/api/integrations/dhis2/connect?server_url=https://dhis2.example.org", {}),
        ("POST", "/api/integrations/dhis2/password-connect", {"json": {"server_url": "ftp://x", "username": "u", "password": "p"}}),
        ("GET", "/api/integrations/dhis2/callback?error=access_denied", {}), ("GET", "/api/integrations/dhis2/callback?code=x&state=y", {}),
        ("GET", "/api/integrations/dhis2/data-sets", {}), ("POST", "/api/integrations/dhis2/import-data-set", {"json": {"local_name": "dhis2_data"}}),
        ("POST", "/api/integrations/dhis2/disconnect", {}),
        # Publishing
        ("GET", "/api/publications", {}), ("GET", "/api/publications/feed/configured-main", {}), ("GET", "/api/publications/feed/missing", {}),
        ("POST", "/api/publications/preview", {"json": publication}), ("POST", "/api/publications/preview", {"json": {"dashboard_id": "missing"}}),
        ("POST", "/api/publications/bundle", {"json": publication}), ("POST", "/api/publications/bundle", {"json": {"dashboard_id": "missing"}}),
        ("POST", "/api/publications/deploy", {"json": publication}),
        # AI
        ("POST", "/api/ai/deidentify/case_reports", {"json": {"limit": 2}}), ("POST", "/api/ai/deidentify/case_reports", {"json": {"limit": "x"}}),
        ("POST", "/api/ai/deidentify/missing", {"json": {}}),
        ("POST", "/api/ai/chat", {"json": {"session_id": "reference-1", "question": "How many cases?", "author": "Reviewer"}}),
        ("POST", "/api/ai/chat", {"json": {"session_id": "x", "question": "?"}}),
        ("GET", "/api/ai/chat?session_id=reference-1", {}), ("GET", "/api/ai/chat", {}),
        ("POST", "/api/ai/chat/1/report", {"json": {"author": "Reviewer"}}), ("POST", "/api/ai/chat/999/report", {"json": {}}),
        ("POST", "/api/ai/chat/1/report", {"json": {}}),
        ("POST", "/api/ai/summaries", {"json": {"title": "Weekly situation", "author": "Reviewer"}}), ("POST", "/api/ai/summaries", {"json": {"title": ""}}),
        ("GET", "/api/ai/summaries", {}), ("GET", "/api/ai/summaries/1", {}), ("GET", "/api/ai/summaries/999", {}),
        ("GET", "/api/ai/summaries/1/export", {}), ("GET", "/api/ai/summaries/999/export", {}),
        ("POST", "/api/ai/summaries/1/review", {"json": {"decision": "approved", "note": "Checked.", "reviewer": "Reviewer"}}),
        ("POST", "/api/ai/summaries/999/review", {"json": {"decision": "approved", "note": "Checked.", "reviewer": "Reviewer"}}),
        ("POST", "/api/ai/summaries/1/review", {"json": {"decision": "approved", "note": ""}}),
        ("GET", "/api/ai/audit", {}),
        ("DELETE", "/api/case_reports/1", {}), ("DELETE", "/api/case_reports/1", {}),
        ("GET", "/api/operations/audit?limit=5", {}),
    ]
    exercised: dict[str, set[int]] = {}
    problems: list[str] = []
    for method, url, options in calls:
        key = find_operation(method, url)
        response = client.request(method, url, **options)
        exercised.setdefault(key, set()).add(response.status_code)
        documented = SPEC["paths"][openapi_path(key.split(" ", 1)[1])][method.lower()]["responses"]
        status = str(response.status_code)
        if status not in documented:
            problems.append(f"{method} {url}: status {status} is not documented ({response.text[:200]})")
            continue
        content = documented[status].get("content")
        if not content:
            continue
        media = response.headers.get("content-type", "").split(";")[0]
        matching = [value for name, value in content.items() if name == media or (name.endswith("/*") and media.startswith(name[:-1]))]
        if not matching:
            problems.append(f"{method} {url}: content type {media} is not documented for {status}")
            continue
        if media == "application/json":
            problems += [f"{method} {url} ({status}) {item}" for item in errors(response.json(), matching[0]["schema"])]
    assert not problems, "\n".join(problems)
    missing = operation_keys() - set(exercised)
    assert not missing, f"Exercise these operations in the live reference test: {sorted(missing)}"
    successes = {key for key, statuses in exercised.items() if any(200 <= status < 400 for status in statuses)}
    # These can only succeed against a real external service, account, or Cloudflare deployment.
    external = {"PUT /api/integrations/cloudflare/account", "POST /api/integrations/dhis2/password-connect",
                "GET /api/integrations/dhis2/data-sets", "POST /api/integrations/dhis2/import-data-set",
                "GET /api/integrations/dhis2/connect", "POST /api/publications/deploy", "POST /api/boundaries",
                "POST /api/connectors/{connector}/sync"}
    assert operation_keys() - successes - external == set(), f"Exercise a successful response for: {sorted(operation_keys() - successes - external)}"
