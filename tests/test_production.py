from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def test_security_headers_readiness_api_token_and_audit(tmp_path: Path, monkeypatch):
    root = create_project("Production Test", tmp_path / "production-test")
    monkeypatch.setenv("PHFRAME_API_TOKEN", "secret-production-token")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    assert client.get("/ready").status_code == 200
    created = client.post("/api/case_reports", json={}, headers={"authorization": "Bearer secret-production-token"})
    assert created.status_code == 422
    audit = client.get("/api/operations/audit").json()["data"]
    assert audit[0]["path"] == "/api/case_reports"
    assert audit[0]["actor"] == "api-token"


def test_request_size_limit(tmp_path: Path, monkeypatch):
    root = create_project("Limits", tmp_path / "limits")
    monkeypatch.setenv("PHFRAME_MAX_BODY_BYTES", "10")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    response = client.post("/api/auth/login", content=b"x" * 11, headers={"content-length": "11"})
    assert response.status_code == 413
