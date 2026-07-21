from pathlib import Path

import pandas as pd

from public_health_framework.cli import main
from public_health_framework.data import DashboardConfig, load_dataset, prepare_dataset
from public_health_framework.report import build_dashboard


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "district": ["Dhaka", "Dhaka", "Khulna"],
            "report_date": ["2026-01-01", "2026-02-01", "2026-01-01"],
            "cases": [10, 15, 8],
            "population": [100_000, 100_000, 80_000],
            "disease": ["Dengue", "Dengue", "Dengue"],
        }
    )


def test_prepare_converts_selected_types():
    config = DashboardConfig("district", "report_date", "cases", "population", "disease")
    prepared = prepare_dataset(sample_frame(), config)
    assert str(prepared["report_date"].dtype).startswith("datetime64")
    assert prepared["cases"].sum() == 33


def test_dashboard_contains_summary(tmp_path: Path):
    config = DashboardConfig("district", "report_date", "cases", "population", "disease")
    output = build_dashboard(prepare_dataset(sample_frame(), config), config, tmp_path / "dashboard.html")
    html = output.read_text(encoding="utf-8")
    assert "Public Health Dashboard" in html
    assert "33" in html
    assert "Dhaka" in html
    assert "Rate per 100,000" in html


def test_cli_generates_dashboard(tmp_path: Path):
    source = tmp_path / "data.csv"
    output = tmp_path / "result.html"
    sample_frame().to_csv(source, index=False)
    result = main(
        [
            "analyze", str(source), "--output", str(output), "--location", "district",
            "--date", "report_date", "--value", "cases", "--population", "population",
        ]
    )
    assert result == 0
    assert output.exists()


def test_load_rejects_unsupported_file(tmp_path: Path):
    source = tmp_path / "data.txt"
    source.write_text("hello", encoding="utf-8")
    try:
        load_dataset(source)
    except ValueError as error:
        assert "Unsupported file type" in str(error)
    else:
        raise AssertionError("Expected an unsupported-file error")

