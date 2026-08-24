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
