from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_data_quality_rule_evaluation(tmp_path: Path):
    root = create_project("Quality Test", tmp_path / "quality-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    common = {
        "disease": "Malaria", "report_date": "2026-08-10",
        "district": "Bandarban", "population": 100_000,
    }
    assert client.post("/api/case_reports", json={
        **common, "case_id": "MAL-001", "status": "confirmed", "cases": 5,
    }).status_code == 201
    assert client.post("/api/case_reports", json={
        **common, "case_id": "MAL-002", "status": "unknown", "cases": -1,
    }).status_code == 201

    range_result = client.get("/api/data-quality/cases_nonnegative").json()["data"]
    assert range_result["total"] == 2
    assert range_result["valid"] == 1
    assert range_result["violations"] == 1
    assert range_result["score"] == 50.0

    allowed_result = client.get("/api/data-quality/valid_case_status").json()["data"]
    assert allowed_result["violations"] == 1
    assert len(client.get("/api/data-quality").json()["data"]) == 2


def test_unknown_data_quality_rule(tmp_path: Path):
    root = create_project("Quality API", tmp_path / "quality-api")
    response = TestClient(PHFrame.from_file(str(root / "phframe.yaml"))).get("/api/data-quality/missing")
    assert response.status_code == 404
