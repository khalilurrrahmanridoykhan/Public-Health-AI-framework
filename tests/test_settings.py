from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_ai_navigation_is_hidden_by_default(tmp_path: Path):
    root = create_project("Floating AI App", tmp_path / "floating-ai-app")
    settings = TestClient(PHFrame.from_file(str(root / "phframe.yaml"))).get("/api/settings").json()["data"]
    assert settings["navigation"]["ai"] == {"label": "AI assistance", "visible": False}


def test_brand_settings_and_assets_are_persisted(tmp_path: Path):
    root = create_project("Branded App", tmp_path / "branded-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={
        "brand_name": "Global Health Hub", "header_title": "Operations",
        "dashboard_title": "Worldwide Event Overview", "primary_color": "#1257a6",
        "default_theme": "dark", "basemap": "esri-imagery", "footer_html": "<p><strong>Example</strong> footer</p>", "show_footer": True,
        "access_mode": "public",
    })
    assert response.status_code == 200
    assert response.json()["data"]["dashboard_title"] == "Worldwide Event Overview"
    assert response.json()["data"]["footer_html"] == "<p><strong>Example</strong> footer</p>"
    assert response.json()["data"]["basemap"] == "esri-imagery"
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


def test_custom_pages_and_rich_text_are_sanitized(tmp_path: Path):
    root = create_project("Page App", tmp_path / "page-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={
        "footer_html": '<p><b>Trusted</b><script>alert(1)</script><a href="javascript:alert(2)">bad</a></p>',
        "pages": [
            {
                "slug": "programme-overview", "title": "Programme overview", "nav_label": "Overview",
                "type": "internal", "url": "", "blocks": [
                    {"id": "intro", "type": "text", "title": "Introduction", "html": '<p>Hello <img src=x onerror=alert(1)><a href="https://example.org">world</a></p>'},
                    {"id": "table", "type": "table", "title": "Records", "dataset": "case_reports"},
                    {"id": "chart", "type": "visualization", "title": "Cases", "source": "kpi|total_cases"},
                ],
            },
            {"slug": "partner-site", "title": "Partner", "nav_label": "Partner", "type": "external", "url": "https://example.org", "blocks": []},
        ],
    })
    assert response.status_code == 200
    settings = response.json()["data"]
    assert "<script" not in settings["footer_html"]
    assert "javascript:" not in settings["footer_html"]
    assert settings["pages"][0]["blocks"][0]["html"] == '<p>Hello <a href="https://example.org" target="_blank" rel="noopener noreferrer">world</a></p>'
    assert settings["pages"][1]["url"] == "https://example.org"


def test_external_pages_require_web_urls(tmp_path: Path):
    root = create_project("Safe Page App", tmp_path / "safe-page-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={"pages": [{
        "slug": "unsafe", "title": "Unsafe", "nav_label": "Unsafe", "type": "external",
        "url": "javascript:alert(1)", "blocks": [],
    }]})
    assert response.status_code == 422
    assert "http or https" in response.json()["error"]["message"]


def test_user_dashboards_are_persisted_and_rich_content_is_sanitized(tmp_path: Path):
    root = create_project("Dashboard App", tmp_path / "dashboard-app")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.put("/api/settings", json={"dashboards": [{
        "id": "programme-overview", "title": "Programme Overview", "description": "Worldwide programme",
        "dataset": "case_reports", "template": "overview", "widgets": [
            {"_id": "intro", "type": "content", "title": "Introduction", "html": '<h2>Heading</h2><p>Read <a href="https://example.org">more</a><script>bad()</script></p>'},
            {"_id": "metric", "type": "field_kpi", "title": "Cases", "dataset": "case_reports", "field": "cases", "operation": "sum"},
        ],
    }]})
    assert response.status_code == 200
    dashboard = response.json()["data"]["dashboards"][0]
    assert dashboard["title"] == "Programme Overview"
    assert dashboard["datasets"] == ["case_reports"]
    assert "<h2>Heading</h2>" in dashboard["widgets"][0]["html"]
    assert "<script" not in dashboard["widgets"][0]["html"]
    assert 'target="_blank"' in dashboard["widgets"][0]["html"]
