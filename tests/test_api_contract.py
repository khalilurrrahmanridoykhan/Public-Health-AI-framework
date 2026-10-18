import json
from pathlib import Path

from public_health_framework.contract import compare_contracts, framework_contract

SNAPSHOT = Path(__file__).resolve().parents[1] / "docs" / "public-api-contract.json"
REGENERATE = "python -m public_health_framework.contract > docs/public-api-contract.json"


def test_public_api_matches_reviewed_contract():
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = framework_contract()
    drift = compare_contracts(expected, actual)
    assert not drift["removed"], f"Breaking public API removals need a deprecation cycle: {drift['removed']}"
    assert not drift["added"], f"New public API must be reviewed; regenerate with `{REGENERATE}`: {drift['added']}"
    assert actual == expected, f"Public API contract is stale; regenerate with `{REGENERATE}`."


def test_contract_comparison_separates_breaking_and_additive_changes():
    base = {"python": ["PHFrame"], "cli": {"serve": ["--port"]}, "http": [{"path": "/api", "methods": ["GET"]}]}
    changed = {"python": ["PHFrame", "Extra"], "cli": {"serve": []}, "http": [{"path": "/api", "methods": ["GET", "POST"]}]}
    drift = compare_contracts(base, changed)
    assert drift["removed"] == ["cli:serve --port"]
    assert drift["added"] == ["http:POST /api", "python:Extra"]


def test_contract_covers_core_surfaces():
    contract = framework_contract()
    assert "PHFrame" in contract["python"]
    assert "--config" in contract["cli"]["serve"]
    assert {"path": "/health", "methods": ["GET"]} in contract["http"]
    assert contract["plugins"]["entry_point_group"] == "phframe.plugins"
