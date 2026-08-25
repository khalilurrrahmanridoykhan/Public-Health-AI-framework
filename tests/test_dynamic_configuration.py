from pathlib import Path

import yaml
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ConnectorSchema
from public_health_framework.connectors import create_connector
from public_health_framework.project import create_project


def test_browser_adds_typed_optional_field_and_persists_it(tmp_path: Path):
    root = create_project("Schema Builder", tmp_path / "schema-builder")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.post(
        "/api/project/datasets/case_reports/fields",
        json={"name": "country_code", "label": "Country code", "type": "string"},
    )
    assert response.status_code == 201
    assert client.get("/api").json()["datasets"]["case_reports"]["fields"]["country_code"]["type"] == "string"
    raw = yaml.safe_load((root / "phframe.yaml").read_text(encoding="utf-8"))
    assert raw["datasets"]["case_reports"]["fields"]["country_code"] == {
        "type": "string", "label": "Country code",
    }
    assert client.post(
        "/api/case_reports",
        json={
            "case_id": "WORLD-1", "disease": "Influenza", "status": "confirmed",
            "report_date": "2026-08-24", "district": "Region 1", "cases": 1,
            "country_code": "EX",
        },
    ).status_code == 201
    grouped = client.get("/api/visualize/case_reports?field=country_code").json()["data"]
    assert grouped["values"] == [{"value": "EX", "count": 1}]
    metric = client.get("/api/visualize/case_reports?field=cases&operation=sum").json()["data"]
    assert metric["value"] == 1.0


def test_browser_creates_and_removes_generic_api_connector(tmp_path: Path):
    root = create_project("API Builder", tmp_path / "api-builder")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    payload = {
        "name": "world_feed", "type": "api", "dataset": "case_reports",
        "base_url": "https://example.test", "resource": "v1/events",
        "records_path": "payload.records", "mapping": {"event.id": "case_id"},
    }
    response = client.post("/api/connectors", json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["type"] == "api"
    assert "base_url" not in response.json()["data"]
    assert yaml.safe_load((root / "phframe.yaml").read_text(encoding="utf-8"))["connectors"]["world_feed"]["type"] == "api"
    assert client.delete("/api/connectors/world_feed").status_code == 204
    assert "world_feed" not in yaml.safe_load((root / "phframe.yaml").read_text(encoding="utf-8"))["connectors"]


def test_generic_api_connector_extracts_common_and_configured_paths():
    schema = ConnectorSchema(
        name="generic", type="api", dataset="events", base_url="https://example.test",
        resource="events", records_path="payload.records", mapping={"source.id": "record_id"},
    )
    connector = create_connector(schema, lambda *_: {"payload": {"records": [{"source": {"id": "A-1"}}]}})
    assert connector.pull() == [{"record_id": "A-1"}]


def test_dhis2_oauth_import_creates_new_typed_dataset_and_connector(tmp_path: Path, monkeypatch):
    root = create_project("DHIS2 Import", tmp_path / "dhis2-import")
    app = PHFrame.from_file(str(root / "phframe.yaml"))
    monkeypatch.setattr(app.dhis2_oauth, "status", lambda: {"connected": True, "server_url": "https://dhis.example", "user": {}})
    response = TestClient(app).post("/api/integrations/dhis2/import-data-set", json={"data_set_id": "abc123", "data_set_name": "Malaria Monthly", "local_name": "malaria_monthly", "schedule_minutes": 30})
    assert response.status_code == 201
    assert response.json()["data"]["dataset"] == "malaria_monthly"
    raw = yaml.safe_load((root / "phframe.yaml").read_text(encoding="utf-8"))
    assert raw["datasets"]["malaria_monthly"]["fields"]["org_unit"]["type"] == "organisation_unit"
    assert raw["connectors"]["malaria_monthly_dhis2"]["resource"] == "abc123"
    assert raw["connectors"]["malaria_monthly_dhis2"]["auth"]["token_env"] == "PHFRAME_DHIS2_OAUTH_TOKEN"
