from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def _client(tmp_path: Path) -> TestClient:
    root = create_project("Publish Test", tmp_path / "publish-test")
    return TestClient(PHFrame.from_file(str(root / "phframe.yaml")))


def test_snapshot_bundle_contains_aggregate_dashboard_only(tmp_path: Path):
    client = _client(tmp_path)
    client.post("/api/case_reports", json={
        "case_id": "secret-case-id", "report_date": "2026-08-01", "disease": "Malaria",
        "status": "confirmed", "district": "Example", "cases": 4,
    })
    payload = {"dashboard_id": "configured-main", "mode": "snapshot"}
    review = client.post("/api/publications/preview", json=payload)
    assert review.status_code == 200
    assert review.json()["data"]["row_level_records"] == 0
    response = client.post("/api/publications/bundle", json=payload)
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert {"index.html", "README.md", "_headers"} <= set(archive.namelist())
        assert "_worker.js" not in archive.namelist()
        html = archive.read("index.html").decode()
    assert "secret-case-id" not in html
    assert "Global Public Health Dashboard" in html


def test_live_bundle_requires_https_and_uses_fixed_proxy(tmp_path: Path):
    client = _client(tmp_path)
    bad = client.post("/api/publications/preview", json={
        "dashboard_id": "configured-main", "mode": "live", "upstream_url": "http://example.org/feed",
    })
    assert bad.status_code == 422
    payload = {"dashboard_id": "configured-main", "mode": "live", "upstream_url": "https://api.example.org/feed", "refresh_minutes": 10}
    response = client.post("/api/publications/bundle", json=payload)
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        worker = archive.read("_worker.js").decode()
    assert 'const UPSTREAM="https://api.example.org/feed"' in worker
    assert "UPSTREAM_API_TOKEN" in worker
    assert "cacheTtl:600" in worker


def test_protected_dashboard_field_is_blocked(tmp_path: Path):
    client = _client(tmp_path)
    created = client.put("/api/settings", json={"dashboards": [{
        "id": "unsafe", "title": "Unsafe", "widgets": [{
            "_id": "identifier", "type": "field_chart", "title": "Cases by identifier",
            "dataset": "case_reports", "field": "case_id",
        }],
    }]})
    assert created.status_code == 200
    response = client.post("/api/publications/preview", json={"dashboard_id": "unsafe", "mode": "snapshot"})
    assert response.status_code == 422
    assert "protected field" in response.json()["error"]["message"]


def test_publication_feed_and_cloudflare_settings(tmp_path: Path):
    client = _client(tmp_path)
    settings = client.put("/api/settings", json={
        "cloudflare_account_id": "account_123", "cloudflare_project_name": "health-dashboard",
        "cloudflare_token_env": "PHFRAME_CLOUDFLARE_TOKEN",
    })
    assert settings.status_code == 200
    assert settings.json()["data"]["cloudflare_project_name"] == "health-dashboard"
    feed = client.get("/api/publications/feed/configured-main")
    assert feed.status_code == 200
    assert set(feed.json()) == {"generated_at", "widgets"}
    deploy = client.post("/api/publications/deploy", json={"dashboard_id": "configured-main", "mode": "snapshot"})
    assert deploy.status_code == 422
    assert "PHFRAME_CLOUDFLARE_TOKEN" in deploy.json()["error"]["message"]


def test_publication_history_is_recorded_without_tokens(tmp_path: Path):
    client = _client(tmp_path)
    app = client.app
    item = app.site_settings.record_publication({
        "dashboard_id": "configured-main", "project_name": "health", "url": "https://health.pages.dev",
        "mode": "snapshot", "refresh_minutes": 15, "privacy": {"approved": True},
    })
    response = client.get("/api/publications").json()
    assert response["data"][0] == item
    stored = json.loads(app.site_settings.path.read_text())
    assert "secret-token-value" not in json.dumps(stored)
