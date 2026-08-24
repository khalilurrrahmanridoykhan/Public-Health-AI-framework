from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_dashboard_configuration_api(tmp_path: Path):
    root = create_project("Dashboard Test", tmp_path / "dashboard-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.get("/api/dashboards/main")
    assert response.status_code == 200
    dashboard = response.json()["data"]
    assert dashboard["label"] == "Global Public Health Dashboard"
    assert [item["type"] for item in dashboard["widgets"]] == ["kpi", "kpi", "chart", "map", "epi_curve"]
    assert client.get("/api/dashboards/missing").status_code == 404


def test_epidemiological_curve_aggregation(tmp_path: Path):
    root = create_project("Curve Test", tmp_path / "curve-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    common = {"disease": "Malaria", "status": "confirmed", "district": "Bandarban"}
    for record in [
        {**common, "case_id": "1", "report_date": "2026-08-01", "cases": 2},
        {**common, "case_id": "2", "report_date": "2026-08-01", "cases": 3},
        {**common, "case_id": "3", "report_date": "2026-08-02", "cases": 1},
    ]:
        assert client.post("/api/case_reports", json=record).status_code == 201
    result = client.get(
        "/api/epi-curve/case_reports?date_field=report_date&value_field=cases"
    ).json()["data"]
    assert result == [
        {"date": "2026-08-01", "value": 5.0},
        {"date": "2026-08-02", "value": 1.0},
    ]
    assert client.get("/api/epi-curve/case_reports?date_field=missing").status_code == 422
