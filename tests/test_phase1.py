from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.project import check_project, create_project


def test_new_project_creates_runnable_structure(tmp_path: Path):
    root = create_project("Dengue Surveillance", tmp_path / "dengue")
    assert (root / "phframe.yaml").exists()
    assert (root / "data" / "phframe.db").exists()
    assert (root / "plugins" / "__init__.py").exists()
    config = ProjectConfig.load(root / "phframe.yaml")
    assert config.name == "Dengue Surveillance"
    assert "case_reports" in config.datasets


def test_check_initializes_database(tmp_path: Path):
    root = create_project("Nutrition Monitoring", tmp_path / "nutrition")
    config, messages = check_project(root / "phframe.yaml")
    assert config.database_path.exists()
    assert messages[-1] == "System check passed"


def test_generated_crud_api(tmp_path: Path):
    root = create_project("Malaria Surveillance", tmp_path / "malaria")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["project"] == "Malaria Surveillance"

    metadata = client.get("/api").json()
    assert metadata["datasets"]["case_reports"]["fields"]["case_id"]["protected"] is True

    payload = {
        "case_id": "MAL-001",
        "disease": "Malaria",
        "status": "confirmed",
        "onset_date": "2026-07-15",
        "report_date": "2026-07-16",
        "district": "Bandarban",
        "cases": 1,
        "population": 500000,
    }
    created = client.post("/api/case_reports", json=payload)
    assert created.status_code == 201
    record = created.json()["data"]
    assert record["id"] == 1
    assert record["cases"] == 1

    listing = client.get("/api/case_reports")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1

    updated = client.patch("/api/case_reports/1", json={"status": "investigated"})
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "investigated"

    deleted = client.delete("/api/case_reports/1")
    assert deleted.status_code == 204
    assert client.get("/api/case_reports/1").status_code == 404


def test_crud_api_reports_validation_errors(tmp_path: Path):
    root = create_project("Outbreak Monitor", tmp_path / "outbreak")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.post("/api/case_reports", json={"case_id": "X"})
    assert response.status_code == 422
    assert "Required fields" in response.json()["error"]["message"]

