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
    for component in ["ph-kpi", "ph-indicator-chart", "ph-epi-curve", "ph-map", "ph-dashboard"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert 'draggable="true"' in javascript.text
    assert "data-visualization" in javascript.text
    assert "data-size" in javascript.text
    assert "ph-dashboard-layout:" in javascript.text
    assert "Dashboard layout saved." in javascript.text
    assert "Bar chart" in javascript.text
    assert "Donut chart" in javascript.text
    assert "Line chart" in javascript.text
    assert ".ph-dashboard-grid" in css.text
    assert ".ph-drag-over" in css.text
    assert 'role="img"' in javascript.text
    for component in ["ph-notification-center", "ph-modal", "ph-confirm"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert 'aria-live="polite"' in javascript.text
    assert "showModal()" in javascript.text
    assert "prefers-reduced-motion" in css.text
    assert ':root[data-theme="dark"]' in css.text
    assert ':root[data-theme="high-contrast"]' in css.text
    assert 'customElements.define("ph-import-wizard"' in javascript.text
    assert 'customElements.define("ph-connector-console"' in javascript.text
    assert "data-theme-choice" in javascript.text
    assert 'data-theme-choice="light"' in javascript.text
    assert 'data-theme-choice="dark"' in javascript.text
    assert 'data-theme-choice="high-contrast"' in javascript.text
    assert "ph-theme-changing" in javascript.text
    assert ".ph-theme-switcher" in css.text
    assert ".ph-theme-switcher:hover, .ph-theme-switcher:focus-within" in css.text
    assert "width: 2.55rem" in css.text
    assert "data-connector-tab" in javascript.text
    assert "setupConnectorNavigation" in javascript.text
    assert ".ph-connectors-sidebar" in css.text
    assert 'customElements.define("ph-data-builder"' in javascript.text
    assert "data-add-widget" in javascript.text
    assert "ph-resize-handle" in javascript.text
    assert "removeWidget" in javascript.text
    assert ".json,.xml" in javascript.text
    assert "Generic REST API" in javascript.text
    assert 'customElements.define("ph-settings-panel"' in javascript.text
    assert 'this.querySelector("form").addEventListener("submit", event => this.save(event))' in javascript.text
    assert '"ne", "se", "sw", "nw"' in javascript.text
    assert "KoboToolbox submissions" in javascript.text
    assert ".ph-builder-layout" in css.text
    assert "data-records-tab" in javascript.text
    assert "data-builder-tab" in javascript.text
    assert "ph-table-pagination" in javascript.text
    assert ".ph-import-shell" in css.text
    assert ".ph-records-workspace" in css.text
    for component in ["ph-rich-editor", "ph-page-table", "ph-custom-page", "ph-page-builder"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert "data-add-block" in javascript.text
    assert "data-page-tab" in javascript.text
    assert 'data-page-panel="create"' in javascript.text
    assert 'data-page-panel="all"' in javascript.text
    assert 'data-page-panel="customize"' in javascript.text
    assert "toggleUrl" in javascript.text
    assert ".ph-pages-sidebar" in css.text
    assert ".ph-field[hidden]" in css.text
    assert "footer_html" in javascript.text
    assert "applyColor" in javascript.text
    assert ".ph-page-canvas" in css.text
    assert ".ph-rich-editor" in css.text
    assert 'customElements.define("ph-ai-workspace"' in javascript.text
    assert "data-ai-form" in javascript.text
    assert "data-deid-form" in javascript.text
    assert "Human-controlled assistance" in javascript.text
    assert "0 protected fields sent" in javascript.text
    assert ".ph-ai-layout" in css.text
    assert "Evidence-aware assistant" in javascript.text
    assert "data-chat-form" in javascript.text
    assert "data-chat-report" in javascript.text
    assert "Are cases increasing over time?" in javascript.text
    assert ".ph-ai-transcript" in css.text
    assert ".ph-ai-composer" in css.text
    assert 'customElements.define("ph-ai-assistant"' in javascript.text
    assert "ph-ai-launcher" in javascript.text
    assert "ph-ai-popup-close" in javascript.text
    assert "<b>Me</b>" in javascript.text
    assert 'author: "Me"' in javascript.text
    assert ".ph-ai-popup" in css.text
    assert "width: min(38rem" in css.text
    for component in ["ph-dashboard-manager", "ph-geo-map"]:
        assert f'customElements.define("{component}"' in javascript.text
    assert "Dashboard templates" in javascript.text
    assert "Executive overview" in javascript.text
    assert "DHIS2 aggregate" in javascript.text
    assert "Worldwide geospatial" in javascript.text
    assert "data-add-content" in javascript.text
    assert "latitude-field" in javascript.text
    assert ".ph-template-grid" in css.text
    assert "pendingGets" in javascript.text
    assert 'PHFrame.loading("Preparing your PHFrame workspace")' in javascript.text
    assert 'PHFrame.loading("Loading dashboard and visualizations")' in javascript.text
    assert "this.metadata = this._metadata" not in javascript.text
    assert ".ph-spinner" in css.text
    assert "@keyframes ph-spin" in css.text
    assert 'this.querySelector(":scope > .ph-dashboard-manager > .ph-template-dialog")' in javascript.text
    assert "data-customize-form" in javascript.text
    assert "Create editable copy" in javascript.text
    assert "Built-in country boundary downloads" in javascript.text
    assert 'PHFrame.send("/api/boundaries", "POST"' in javascript.text
    assert "renderBoundary" in javascript.text
    assert ".ph-boundary-map" in css.text
    assert "ph-boundary-countries" in javascript.text
    assert "Search country name or ISO3" in javascript.text
    assert 'PHFrame.get("/api/boundaries/countries")' in javascript.text
    assert "setupSettingsNavigation" in javascript.text
    assert 'role="tablist"' in javascript.text
    assert "data-settings-tab" in javascript.text
    assert ".ph-settings-sidebar" in css.text
    assert ".ph-settings-tab-active" in css.text


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
