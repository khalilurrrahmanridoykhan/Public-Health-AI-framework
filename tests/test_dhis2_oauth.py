from pathlib import Path

import pytest

from public_health_framework.dhis2_oauth import DHIS2OAuth


def test_dhis2_oauth_connects_encrypts_discovers_and_disconnects(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PHFRAME_DHIS2_CLIENT_ID", "phframe")
    monkeypatch.setenv("PHFRAME_DHIS2_CLIENT_SECRET", "client-secret")
    oauth = DHIS2OAuth(tmp_path)
    url = oauth.begin("https://dhis.example", "https://health.example/api/integrations/dhis2/callback")
    assert url.startswith("https://dhis.example/uaa/oauth/authorize?")
    pending = oauth._load(oauth.state_path)

    def request(url, **kwargs):
        if url.endswith("/uaa/oauth/token"):
            return {"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_in": 3600}
        if "/api/me" in url:
            return {"id": "u1", "username": "analyst", "displayName": "Health Analyst"}
        return {"dataSets": [{"id": "abc123", "displayName": "Malaria Cases"}]}

    monkeypatch.setattr(oauth, "_request_json", request)
    status = oauth.complete("authorization-code", pending["state"])
    assert status["connected"] is True
    assert status["user"]["displayName"] == "Health Analyst"
    assert b"secret-access" not in oauth.credentials_path.read_bytes()
    assert oauth.data_sets() == [{"id": "abc123", "name": "Malaria Cases"}]
    oauth.disconnect()
    assert oauth.status()["connected"] is False


def test_dhis2_oauth_rejects_invalid_server_and_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PHFRAME_DHIS2_CLIENT_ID", "phframe")
    monkeypatch.setenv("PHFRAME_DHIS2_CLIENT_SECRET", "client-secret")
    oauth = DHIS2OAuth(tmp_path)
    with pytest.raises(ValueError, match="HTTPS"):
        oauth.begin("http://dhis.example", "https://health.example/callback")
    oauth.begin("https://dhis.example", "https://health.example/callback")
    with pytest.raises(ValueError, match="state"):
        oauth.complete("code", "wrong-state")


def test_dhis2_oauth_can_use_encrypted_project_client_configuration(tmp_path: Path):
    oauth = DHIS2OAuth(tmp_path)
    oauth.configure_client("project-client", "project-secret")
    assert oauth.status()["available"] is True
    assert oauth.client_id == "project-client"
    assert b"project-secret" not in oauth.client_path.read_bytes()
