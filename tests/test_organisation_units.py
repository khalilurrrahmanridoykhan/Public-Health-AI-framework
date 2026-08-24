from pathlib import Path

import pytest
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.project import create_project


def test_organisation_unit_hierarchy_api(tmp_path: Path):
    root = create_project("Hierarchy Test", tmp_path / "hierarchy-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    listing = client.get("/api/organisation-units").json()
    assert listing["count"] == 3
    assert listing["roots"] == ["global"]

    site = client.get("/api/organisation-units/example_site").json()["data"]
    assert site["parent"] == "example_region"
    assert [item["code"] for item in site["ancestors"]] == ["global", "example_region"]
    region = client.get("/api/organisation-units/example_region").json()["data"]
    assert region["children"] == ["example_site"]
    assert client.get("/api/organisation-units/missing").status_code == 404


def test_organisation_unit_referential_validation(tmp_path: Path):
    root = create_project("Hierarchy Records", tmp_path / "hierarchy-records")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    payload = {
        "case_id": "MAL-300", "disease": "Malaria", "status": "confirmed",
        "report_date": "2026-08-15", "district": "Bandarban", "cases": 1,
        "reporting_unit": "example_site",
    }
    assert client.post("/api/case_reports", json=payload).status_code == 201
    invalid = client.post(
        "/api/case_reports", json={**payload, "case_id": "MAL-301", "reporting_unit": "missing"}
    )
    assert invalid.status_code == 422
    assert "unknown organisation unit" in invalid.json()["error"]["message"]


def test_hierarchy_rejects_cycles(tmp_path: Path):
    root = create_project("Hierarchy Config", tmp_path / "hierarchy-config")
    path = root / "phframe.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "  global:\n    name: Global\n    level: global\n",
        "  global:\n    name: Global\n    level: global\n    parent: example_site\n",
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="contains a cycle"):
        ProjectConfig.load(path)
