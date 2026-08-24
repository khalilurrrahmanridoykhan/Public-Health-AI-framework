from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def _client(tmp_path: Path) -> TestClient:
    root = create_project("Indicator Test", tmp_path / "indicator-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    for payload in [
        {
            "case_id": "MAL-001", "disease": "Malaria", "status": "confirmed",
            "report_date": "2026-07-10", "district": "Bandarban", "cases": 10,
            "population": 100_000,
        },
        {
            "case_id": "MAL-002", "disease": "Malaria", "status": "suspected",
            "report_date": "2026-08-10", "district": "Rangamati", "cases": 5,
            "population": 200_000,
        },
    ]:
        assert client.post("/api/case_reports", json=payload).status_code == 201
    return client


def test_indicator_metadata_and_sum(tmp_path: Path):
    client = _client(tmp_path)
    metadata = client.get("/api").json()
    assert metadata["indicators"]["total_cases"]["operation"] == "sum"
    result = client.get("/api/indicators/total_cases").json()["data"]
    assert result["value"] == 15.0


def test_indicator_filters_and_reporting_period(tmp_path: Path):
    client = _client(tmp_path)
    filtered = client.get("/api/indicators/total_cases?district=Bandarban").json()["data"]
    assert filtered["value"] == 10.0
    period = client.get(
        "/api/indicators/total_cases?start=2026-08-01&end=2026-08-31"
    ).json()["data"]
    assert period["value"] == 5.0


def test_rate_and_invalid_filter(tmp_path: Path):
    client = _client(tmp_path)
    result = client.get("/api/indicators/incidence_per_100000").json()["data"]
    assert result["value"] == 5.0
    invalid = client.get("/api/indicators/total_cases?unknown=value")
    assert invalid.status_code == 422
    assert "Unknown filter field" in invalid.json()["error"]["message"]
