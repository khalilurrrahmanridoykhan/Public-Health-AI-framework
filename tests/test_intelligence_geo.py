from pathlib import Path

import pandas as pd
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.intelligence import profile_frame
from public_health_framework.intelligence_geo import infer_geography
from public_health_framework.project import create_project


def test_geography_infers_hierarchy_points_and_parent_conflicts():
    rows = [
        {"country": "A", "region": "R1", "district": "D1", "facility": "F1", "latitude": 10, "longitude": 20},
        {"country": "A", "region": "R2", "district": "D1", "facility": "F2", "latitude": 11, "longitude": 21},
    ]
    model = infer_geography(rows, profile_frame(pd.DataFrame(rows)))
    assert model["filter_fields"] == ["country", "region", "district", "facility"]
    assert model["map_ready"] is True
    assert model["map_coverage_percent"] == 100
    assert any(issue["rule"] == "multiple_parents" and issue["child_field"] == "district" for issue in model["issues"])


def test_geography_model_api_persists_result(tmp_path: Path):
    root = create_project("Geography Review", tmp_path / "geography-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    content = b"case_id,disease,status,report_date,district,country,cases\nA,Malaria,confirmed,2026-01-01,North,Exampleland,2\n"
    version_id = client.post("/api/browser-import/case_reports/preview?filename=geo.csv", content=content).json()["data"]["version"]["id"]
    created = client.post(f"/api/staging/{version_id}/geography")
    assert created.status_code == 201
    assert created.json()["data"]["model"]["filter_fields"] == ["country", "district"]
    assert client.get(f"/api/staging/{version_id}/geography").json()["data"]["id"] == created.json()["data"]["id"]
