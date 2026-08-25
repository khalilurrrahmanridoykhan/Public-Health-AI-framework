from datetime import datetime, timedelta
from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.cli import main
from public_health_framework.config import ProjectConfig
from public_health_framework.project import create_project
from public_health_framework.storage import Storage
from public_health_framework.sync import connector_due, sync_connector


def configured_project(tmp_path: Path) -> ProjectConfig:
    root = create_project("Sync Test", tmp_path / "sync-test")
    path = root / "phframe.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "connectors: {}",
        """connectors:
  kobo_cases:
    type: kobo
    dataset: case_reports
    base_url: https://kf.example
    resource: malaria-asset
    schedule_minutes: 60
    mapping:
      case_id: case_id
      disease: disease
      status: status
      report_date: report_date
      district: district
      cases: cases""",
    ), encoding="utf-8")
    return ProjectConfig.load(path)


def test_connector_sync_imports_and_audits(tmp_path: Path):
    config = configured_project(tmp_path)
    payload = {"results": [{
        "case_id": "K-1", "disease": "Malaria", "status": "confirmed",
        "report_date": "2026-08-24", "district": "Bandarban", "cases": 3,
    }], "next": None}
    result = sync_connector(config, "kobo_cases", transport=lambda url, headers, timeout: payload)
    assert result.status == "completed"
    assert result.fetched_rows == result.imported_rows == 1
    storage = Storage(config)
    assert storage.sync_history()[0]["connector"] == "kobo_cases"
    assert len(storage.list(config.datasets["case_reports"])) == 1
    version = storage.dataset_version(result.version_id)
    assert version["source"] == "connector:kobo_cases"
    assert version["source_kind"] == "kobo"
    assert version["status"] == "approved"
    assert version["profile"]["row_count"] == 1


def test_failed_sync_is_audited_and_atomic(tmp_path: Path):
    config = configured_project(tmp_path)
    payload = {"results": [{"case_id": "incomplete"}], "next": None}
    result = sync_connector(config, "kobo_cases", transport=lambda url, headers, timeout: payload)
    assert result.status == "failed"
    assert result.imported_rows == 0
    assert result.errors
    assert Storage(config).list(config.datasets["case_reports"]) == []


def test_due_schedule_and_connector_metadata_api(tmp_path: Path):
    config = configured_project(tmp_path)
    assert connector_due(config, "kobo_cases") is True
    Storage(config).record_sync("kobo_cases", "case_reports", "completed", 0, 0, [])
    assert connector_due(config, "kobo_cases", datetime.now().astimezone() + timedelta(minutes=30)) is False
    assert connector_due(config, "kobo_cases", datetime.now().astimezone() + timedelta(minutes=61)) is True
    client = TestClient(PHFrame(config))
    metadata = client.get("/api/connectors").json()["data"][0]
    assert metadata["name"] == "kobo_cases"
    assert "base_url" not in metadata
    assert client.get("/api/syncs").json()["data"][0]["status"] == "completed"


def test_sync_cli_handles_no_due_connectors(tmp_path: Path, capsys):
    root = create_project("Empty Sync", tmp_path / "empty-sync")
    assert main(["sync", "--all", "--due", "--config", str(root / "phframe.yaml")]) == 0
    assert "No connector synchronizations are due" in capsys.readouterr().out
