from pathlib import Path

import pandas as pd
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.intelligence import profile_frame
from public_health_framework.intelligence_semantic import compile_semantic_model
from public_health_framework.project import create_project


def test_semantic_model_builds_governed_measures_and_compatible_views():
    profile = profile_frame(pd.DataFrame({"report_date": ["2026-01-01", "2026-02-01"], "district": ["A", "B"], "cases": [2, 4], "patient_id": ["P1", "P2"]}))
    model = compile_semantic_model(profile, {"score": 100, "readiness": "ready", "blocker_count": 0}, {"map_ready": True, "filter_fields": ["district"]})
    assert any(item["id"] == "sum_cases" for item in model["measures"])
    assert {item["view"] for item in model["recommendations"]} >= {"number", "line", "bar", "map", "table"}
    assert next(item for item in model["fields"] if item["name"] == "patient_id")["role"] == "identifier"
    assert all(item["reason"] for item in model["recommendations"])


def test_semantic_contract_api_versions_and_approves(tmp_path: Path):
    root = create_project("Semantic Review", tmp_path / "semantic-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    content = b"case_id,disease,status,report_date,district,cases\nA,Malaria,confirmed,2026-01-01,North,2\n"
    version_id = client.post("/api/browser-import/case_reports/preview?filename=semantic.csv", content=content).json()["data"]["version"]["id"]
    client.post(f"/api/staging/{version_id}/geography")
    created = client.post(f"/api/staging/{version_id}/semantic")
    assert created.status_code == 201
    contract = created.json()["data"]
    assert contract["contract_version"] == 1
    assert contract["status"] == "draft"
    approved = client.patch(f"/api/staging/{version_id}/semantic", json={"model_id": contract["id"]})
    assert approved.json()["data"]["status"] == "approved"
