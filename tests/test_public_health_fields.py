from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.project import create_project


def test_generated_project_uses_public_health_fields(tmp_path: Path):
    root = create_project("Field Types", tmp_path / "field-types")
    config = ProjectConfig.load(root / "phframe.yaml")
    fields = config.datasets["case_reports"].fields
    assert fields["case_id"].type == "identifier"
    assert fields["disease"].type == "disease_code"
    assert fields["patient_age"].type == "age"
    assert fields["epi_week"].type == "epi_week"


def test_age_and_epi_week_validation(tmp_path: Path):
    root = create_project("Validated Fields", tmp_path / "validated-fields")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    payload = {
        "case_id": "MAL-100", "disease": "Malaria", "status": "confirmed",
        "report_date": "2026-08-12", "district": "Bandarban", "cases": 1,
        "patient_age": 42, "epi_week": "2026-W33",
    }
    created = client.post("/api/case_reports", json=payload)
    assert created.status_code == 201
    assert created.json()["data"]["patient_age"] == 42

    invalid_age = client.post("/api/case_reports", json={**payload, "case_id": "MAL-101", "patient_age": 131})
    assert invalid_age.status_code == 422
    assert "valid age" in invalid_age.json()["error"]["message"]
    fractional_age = client.post(
        "/api/case_reports", json={**payload, "case_id": "MAL-103", "patient_age": 12.5}
    )
    assert fractional_age.status_code == 422
    invalid_week = client.post("/api/case_reports", json={**payload, "case_id": "MAL-102", "epi_week": "2026-W99"})
    assert invalid_week.status_code == 422
    assert "valid epi_week" in invalid_week.json()["error"]["message"]


def test_categorical_public_health_fields(tmp_path: Path):
    root = create_project("Categorical Fields", tmp_path / "categorical-fields")
    path = root / "phframe.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "      epi_week:\n        type: epi_week\n",
        "      epi_week:\n        type: epi_week\n      sex:\n        type: sex\n      classification:\n        type: case_classification\n",
    )
    path.write_text(text, encoding="utf-8")
    client = TestClient(PHFrame.from_file(str(path)))
    base = {
        "case_id": "MAL-200", "disease": "Malaria", "status": "confirmed",
        "report_date": "2026-08-12", "district": "Bandarban", "cases": 1,
    }
    valid = client.post("/api/case_reports", json={**base, "sex": "female", "classification": "probable"})
    assert valid.status_code == 201
    invalid = client.post("/api/case_reports", json={**base, "case_id": "MAL-201", "sex": "not-known"})
    assert invalid.status_code == 422
