from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_frontend_shell_and_assets(tmp_path: Path):
    root = create_project("Frontend Test", tmp_path / "frontend-test")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    app = client.get("/app")
    assert app.status_code == 200
    assert "<ph-app-shell>" in app.text
    assert 'href="/assets/phframe.css"' in app.text
    css = client.get("/assets/phframe.css")
    assert css.status_code == 200
    assert "--ph-color-primary" in css.text
    javascript = client.get("/assets/phframe.js")
    assert javascript.status_code == 200
    assert 'customElements.define("ph-app-shell"' in javascript.text
    assert "ph-route" in javascript.text
    for component in ["ph-data-form", "ph-case-table", "ph-filter-bar", "ph-org-unit-select", "ph-quality-panel"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert "fields[name].protected" in javascript.text
    assert 'role="status"' in javascript.text
    for component in ["ph-kpi", "ph-indicator-chart", "ph-epi-curve", "ph-dashboard"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert 'role="img"' in javascript.text
    for component in ["ph-notification-center", "ph-modal", "ph-confirm"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert 'aria-live="polite"' in javascript.text
    assert "showModal()" in javascript.text
    assert "prefers-reduced-motion" in css.text
    assert ':root[data-theme="dark"]' in css.text
    assert ':root[data-theme="high-contrast"]' in css.text


def test_frontend_metadata_includes_ui_configuration(tmp_path: Path):
    root = create_project("Localized UI", tmp_path / "localized-ui")
    metadata = TestClient(PHFrame.from_file(str(root / "phframe.yaml"))).get("/api").json()
    assert metadata["ui"] == {"theme": "light", "locale": "en", "translations": {}}


def test_record_collection_supports_saved_filters(tmp_path: Path):
    root = create_project("Frontend Filters", tmp_path / "frontend-filters")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    base = {"disease": "Malaria", "report_date": "2026-08-20", "district": "Bandarban", "cases": 1}
    client.post("/api/case_reports", json={**base, "case_id": "1", "status": "confirmed"})
    client.post("/api/case_reports", json={**base, "case_id": "2", "status": "suspected"})
    response = client.get("/api/case_reports?filter=confirmed_cases")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["status"] == "confirmed"
