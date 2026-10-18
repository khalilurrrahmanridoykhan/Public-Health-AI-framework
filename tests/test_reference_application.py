"""Phase 8.5: the packaged malaria surveillance reference application works end to end."""

import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.importer import import_dataset
from public_health_framework.project import check_project

EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "malaria-surveillance"
SAMPLE_DATA = EXAMPLE_ROOT.parent / "malaria_surveillance.csv"


def _isolated_copy(tmp_path: Path) -> ProjectConfig:
    """Load the example configuration into a scratch project directory, so a test
    database is never written into the repository's own examples/ directory."""
    config_path = tmp_path / "phframe.yaml"
    shutil.copy(EXAMPLE_ROOT / "phframe.yaml", config_path)
    return ProjectConfig.load(config_path)


def test_configuration_is_current_and_declares_the_surveillance_schema():
    config, report = check_project(EXAMPLE_ROOT / "phframe.yaml")
    assert config.version == 1 and config.warnings == ()
    assert not any(line.startswith("Warning:") for line in report)
    assert set(config.datasets["facility_reports"].fields) == {
        "district", "report_date", "facility_type", "cases", "population", "confirmed_cases", "tested",
    }
    assert set(config.indicators) == {"total_cases", "incidence_per_100000", "test_positivity_percentage"}
    assert set(config.data_quality_rules) == {"cases_nonnegative", "tested_nonnegative", "valid_facility_type"}
    assert "main" in config.dashboards
    assert len(config.organisation_units) == 6


def test_the_published_sample_data_imports_cleanly(tmp_path: Path):
    config = _isolated_copy(tmp_path)
    result = import_dataset(config, "facility_reports", SAMPLE_DATA, dry_run=False)
    assert result.status == "completed"
    assert result.imported_rows == 10
    assert not result.errors


def test_indicators_data_quality_and_dashboard_serve_correctly(tmp_path: Path):
    config = _isolated_copy(tmp_path)
    import_dataset(config, "facility_reports", SAMPLE_DATA, dry_run=False)
    client = TestClient(PHFrame(config).asgi)

    total_cases = client.get("/api/indicators/total_cases").json()["data"]
    assert total_cases["value"] == 595.0  # sum of the cases column across all 10 sample rows

    incidence = client.get("/api/indicators/incidence_per_100000?district=Sylhet").json()["data"]
    assert incidence["value"] == pytest.approx((93 + 105) / (4_000_000 * 2) * 100_000)

    positivity = client.get("/api/indicators/test_positivity_percentage?district=Dhaka").json()["data"]
    assert positivity["value"] == pytest.approx((31 + 27) / (180 + 165) * 100)

    quality = client.get("/api/data-quality").json()["data"]
    assert len(quality) == 3
    assert all(rule["violations"] == 0 for rule in quality), quality

    assert client.get("/api/thresholds/high_incidence?district=Sylhet").json()["data"]["status"] == "triggered"
    assert client.get("/api/thresholds/high_incidence?district=Dhaka").json()["data"]["status"] == "normal"

    dashboard = client.get("/api/dashboards/main").json()["data"]
    assert len(dashboard["widgets"]) == 6

    assert client.get("/app").status_code == 200
