from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.intelligence import profile_frame
from public_health_framework.intelligence_quality import evaluate_quality
from public_health_framework.project import create_project

import pandas as pd


def test_quality_engine_finds_duplicates_missing_dates_aliases_and_coordinates():
    rows = [
        {"report_date": "2099-01-01", "status": "Confirmed", "latitude": 95, "cases": 2},
        {"report_date": None, "status": "confirmed", "latitude": 10, "cases": 2},
        {"report_date": None, "status": "confirmed", "latitude": 10, "cases": 2},
    ]
    report = evaluate_quality(rows, profile_frame(pd.DataFrame(rows)))
    rules = {issue["rule"] for issue in report["issues"]}
    assert {"missing_values", "future_date", "coordinate_range", "category_alias", "duplicate_row"} <= rules
    assert report["readiness"] == "blocked"
    assert report["score"] < 100


def test_quality_report_is_persisted_and_available_by_api(tmp_path: Path):
    root = create_project("Quality Review", tmp_path / "quality-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    content = b"case_id,disease,status,report_date,district,cases\nA,Malaria,confirmed,2026-01-01,North,2\nA,Malaria,confirmed,2026-01-01,North,2\n"
    preview = client.post("/api/browser-import/case_reports/preview?filename=quality.csv", content=content)
    assert preview.status_code == 200
    version_id = preview.json()["data"]["version"]["id"]
    quality = preview.json()["data"]["quality"]
    assert quality["readiness"] == "blocked"
    assert any(issue["rule"] == "duplicate_row" for issue in quality["issues"])
    assert client.get(f"/api/staging/{version_id}/quality").json()["data"]["id"] == quality["id"]
    rerun = client.post(f"/api/staging/{version_id}/quality")
    assert rerun.status_code == 201
    assert rerun.json()["data"]["id"] > quality["id"]
