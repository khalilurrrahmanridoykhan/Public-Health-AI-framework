from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_saved_filters_and_grouped_dimensions(tmp_path: Path):
    root = create_project("Dimension Test", tmp_path / "dimension-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    common = {"disease": "Malaria", "report_date": "2026-08-10", "cases": 1}
    records = [
        {**common, "case_id": "1", "status": "confirmed", "district": "Bandarban"},
        {**common, "case_id": "2", "status": "suspected", "district": "Bandarban"},
        {**common, "case_id": "3", "status": "confirmed", "district": "Rangamati"},
    ]
    for record in records:
        assert client.post("/api/case_reports", json=record).status_code == 201

    assert client.get("/api/filters").json()["data"][0]["name"] == "confirmed_cases"
    grouped = client.get("/api/dimensions/cases_by_district").json()["data"]
    assert grouped["values"] == [
        {"value": "Bandarban", "count": 2},
        {"value": "Rangamati", "count": 1},
    ]
    confirmed = client.get("/api/dimensions/confirmed_cases_by_district").json()["data"]
    assert confirmed["filters"] == {"status": "confirmed"}
    assert confirmed["values"] == [
        {"value": "Bandarban", "count": 1},
        {"value": "Rangamati", "count": 1},
    ]


def test_dimension_query_filter_and_errors(tmp_path: Path):
    root = create_project("Dimension API", tmp_path / "dimension-api")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    assert client.get("/api/dimensions/missing").status_code == 404
    assert client.get("/api/dimensions/cases_by_district?unknown=value").status_code == 422
