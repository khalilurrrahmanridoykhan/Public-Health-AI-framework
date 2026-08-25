from pathlib import Path
from time import perf_counter
from starlette.testclient import TestClient
from public_health_framework.application import PHFrame
from public_health_framework.project import create_project

def test_liveness_baseline_and_accessibility_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PHFRAME_RATE_LIMIT", "1000")
    root = create_project("Certification", tmp_path / "certification"); client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    started = perf_counter()
    for _ in range(250): assert client.get("/health").status_code == 200
    assert perf_counter() - started < 10
    app = client.get("/app").text; javascript = client.get("/assets/phframe.js").text; css = client.get("/assets/phframe.css").text
    assert 'href="#main"' in javascript
    assert 'aria-label="Primary"' in javascript
    assert 'aria-live="polite"' in javascript
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert '<meta name="viewport"' in app

def test_collection_reports_database_total(tmp_path: Path):
    root = create_project("Pagination", tmp_path / "pagination"); client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.get("/api/case_reports?limit=1").json()
    assert response["total"] >= response["count"]
