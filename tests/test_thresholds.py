from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def _client(tmp_path: Path) -> TestClient:
    root = create_project("Threshold Test", tmp_path / "threshold-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    common = {
        "disease": "Malaria", "district": "Bandarban", "population": 100_000,
    }
    for record in [
        {**common, "case_id": "1", "status": "confirmed", "report_date": "2026-08-10", "cases": 7},
        {**common, "case_id": "2", "status": "suspected", "report_date": "2026-08-11", "cases": 4},
        {**common, "case_id": "3", "status": "confirmed", "report_date": "2026-07-01", "cases": 2},
    ]:
        assert client.post("/api/case_reports", json=record).status_code == 201
    return client


def test_threshold_triggers_for_epidemiological_week(tmp_path: Path):
    client = _client(tmp_path)
    result = client.get("/api/thresholds/high_weekly_case_count?period=2026-W33").json()["data"]
    assert result["actual"] == 11.0
    assert result["threshold"] == 10.0
    assert result["triggered"] is True
    assert result["status"] == "triggered"
    assert result["severity"] == "warning"


def test_threshold_respects_saved_filter(tmp_path: Path):
    client = _client(tmp_path)
    result = client.get(
        "/api/thresholds/high_weekly_case_count?period=2026-W33&filter=confirmed_cases"
    ).json()["data"]
    assert result["actual"] == 7.0
    assert result["triggered"] is False
    assert result["status"] == "normal"
    assert result["filters"] == {"status": "confirmed"}


def test_threshold_list_and_missing_rule(tmp_path: Path):
    client = _client(tmp_path)
    assert client.get("/api/thresholds").json()["data"][0]["name"] == "high_weekly_case_count"
    assert client.get("/api/thresholds/missing").status_code == 404
