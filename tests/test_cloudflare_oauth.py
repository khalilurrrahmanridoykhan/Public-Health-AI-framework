from __future__ import annotations

from cryptography.fernet import Fernet

from public_health_framework.cloudflare import CloudflareOAuth


def test_cloudflare_oauth_authorizes_encrypts_and_selects_account(tmp_path, monkeypatch):
    monkeypatch.setenv("PHFRAME_CLOUDFLARE_CLIENT_ID", "client-id")
    monkeypatch.setenv("PHFRAME_CLOUDFLARE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("PHFRAME_CREDENTIAL_KEY", Fernet.generate_key().decode())
    oauth = CloudflareOAuth(tmp_path)
    url = oauth.begin("https://health.example/api/integrations/cloudflare/callback")
    assert url.startswith("https://dash.cloudflare.com/oauth2/auth?")
    assert "code_challenge=" in url
    pending = oauth._load(oauth.state_path)

    def request(url, form=None, bearer=""):
        if url == oauth.token_url:
            return {"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_in": 3600}
        return {"success": True, "result": [{"id": "account-a", "name": "Health A"}, {"id": "account-b", "name": "Health B"}]}

    monkeypatch.setattr(oauth, "_request_json", request)
    result = oauth.complete("authorization-code", pending["state"])
    assert result["connected"] is True
    assert result["account"]["id"] == "account-a"
    assert b"secret-access" not in oauth.credentials_path.read_bytes()
    assert oauth.select_account("account-b")["account"]["name"] == "Health B"
    assert oauth.deployment_credentials() == ("account-b", "secret-access")
    oauth.disconnect()
    assert oauth.status()["connected"] is False


def test_cloudflare_oauth_rejects_invalid_state(tmp_path, monkeypatch):
    monkeypatch.setenv("PHFRAME_CLOUDFLARE_CLIENT_ID", "client-id")
    monkeypatch.setenv("PHFRAME_CLOUDFLARE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("PHFRAME_CREDENTIAL_KEY", Fernet.generate_key().decode())
    oauth = CloudflareOAuth(tmp_path)
    oauth.begin("https://health.example/callback")
    try:
        oauth.complete("code", "wrong-state")
    except ValueError as error:
        assert "state" in str(error)
    else:
        raise AssertionError("Invalid OAuth state was accepted")
