from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_brand_settings_and_assets_are_persisted(tmp_path: Path):
    root = create_project("Branded App", tmp_path / "branded-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={
        "brand_name": "Global Health Hub", "header_title": "Operations",
        "dashboard_title": "Worldwide Event Overview", "primary_color": "#1257a6",
        "default_theme": "dark", "footer_text": "Example footer", "show_footer": True,
        "access_mode": "public",
    })
    assert response.status_code == 200
    assert response.json()["data"]["dashboard_title"] == "Worldwide Event Overview"
    assert client.post(
        "/api/settings/assets/logo?filename=brand.png", content=b"valid-enough-image-bytes"
    ).status_code == 200
    assert client.get("/assets/project/logo").content == b"valid-enough-image-bytes"
    assert (root / "data" / "phframe-settings.json").exists()
    assert client.get("/assets/phframe-logo.png").headers["content-type"] == "image/png"


def test_private_mode_requires_login_and_supports_logout(tmp_path: Path):
    root = create_project("Private App", tmp_path / "private-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    enabled = client.put("/api/settings", json={
        "access_mode": "private", "username": "admin", "password": "strong-password-123",
    })
    assert enabled.status_code == 200
    assert client.get("/api").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    login = client.post("/api/auth/login", json={"username": "admin", "password": "strong-password-123"})
    assert login.status_code == 200
    assert client.get("/api").status_code == 200
    status = client.get("/api/auth/status").json()["data"]
    assert status == {"access_mode": "private", "authenticated": True}
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api").status_code == 401


def test_private_mode_cannot_be_enabled_without_a_user(tmp_path: Path):
    root = create_project("Safe Private App", tmp_path / "safe-private-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={"access_mode": "private"})
    assert response.status_code == 422
    assert "Create a login user" in response.json()["error"]["message"]
