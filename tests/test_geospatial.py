from pathlib import Path

import yaml
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_geospatial_endpoint_aggregates_and_privacy_rounds_coordinates(tmp_path: Path):
    root = create_project("Map App", tmp_path / "map-app")
    config_path = root / "phframe.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["datasets"]["sites"] = {"label": "Sites", "fields": {"name": {"type": "string", "required": True}, "latitude": {"type": "number", "required": True}, "longitude": {"type": "number", "required": True}}}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    client = TestClient(PHFrame.from_file(str(config_path)))
    client.post("/api/sites", json={"name": "A", "latitude": 23.78061, "longitude": 90.40701})
    client.post("/api/sites", json={"name": "B", "latitude": 23.78149, "longitude": 90.40849})
    response = client.get("/api/geospatial/sites?latitude=latitude&longitude=longitude")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["precision"] == 2
    assert data["source_rows"] == 2
    assert sum(point["count"] for point in data["points"]) == 2
    assert "aggregated" in data["privacy"]


def test_geospatial_endpoint_rejects_non_numeric_coordinates(tmp_path: Path):
    root = create_project("Bad Map App", tmp_path / "bad-map-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.get("/api/geospatial/case_reports?latitude=district&longitude=disease")
    assert response.status_code == 422
