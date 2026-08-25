"""Cloudflare OAuth connection storage and token lifecycle."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken


class CloudflareOAuth:
    authorize_url = "https://dash.cloudflare.com/oauth2/auth"
    token_url = "https://dash.cloudflare.com/oauth2/token"
    revoke_url = "https://dash.cloudflare.com/oauth2/revoke"
    api_url = "https://api.cloudflare.com/client/v4"
    default_broker_url = "https://phframe-auth.82.25.92.211.nip.io"

    def __init__(self, root: Path):
        self.directory = Path(root) / "data"
        self.credentials_path = self.directory / ".cloudflare-oauth"
        self.state_path = self.directory / ".cloudflare-oauth-state"
        self.key_path = self.directory / ".credential-key"

    @property
    def client_id(self) -> str: return os.getenv("PHFRAME_CLOUDFLARE_CLIENT_ID", "").strip()

    @property
    def client_secret(self) -> str: return os.getenv("PHFRAME_CLOUDFLARE_CLIENT_SECRET", "").strip()

    @property
    def scopes(self) -> str:
        return os.getenv("PHFRAME_CLOUDFLARE_SCOPES", "workers-platform.read workers-platform.write").strip()

    @property
    def broker_url(self) -> str: return os.getenv("PHFRAME_CLOUDFLARE_BROKER_URL", self.default_broker_url).rstrip("/")

    def status(self) -> dict[str, Any]:
        credentials = self._load(self.credentials_path) or {}
        accounts = credentials.get("accounts", [])
        selected = credentials.get("account_id", "")
        account = next((item for item in accounts if item.get("id") == selected), None)
        return {
            "available": bool((self.client_id and self.client_secret) or self.broker_url),
            "connected": bool(credentials.get("access_token") and selected),
            "account": {"id": selected, "name": (account or {}).get("name", "")},
            "accounts": [{"id": str(item.get("id", "")), "name": str(item.get("name", ""))} for item in accounts],
            "expires_at": credentials.get("expires_at", ""),
        }

    def begin(self, redirect_uri: str) -> str:
        if not self.client_id or not self.client_secret: return self.begin_broker(redirect_uri.replace("/callback", "/broker/callback"))
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self._save(self.state_path, {"state": state, "verifier": verifier, "redirect_uri": redirect_uri, "created_at": datetime.now(timezone.utc).isoformat()})
        return self.authorize_url + "?" + urlencode({"response_type": "code", "client_id": self.client_id, "redirect_uri": redirect_uri, "scope": self.scopes, "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})

    def begin_broker(self, return_uri: str) -> str:
        parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(self.broker_url)
        if parsed.scheme != "https" or not parsed.netloc: raise ValueError("PHFRAME_CLOUDFLARE_BROKER_URL must use HTTPS.")
        state = secrets.token_urlsafe(32)
        self._save(self.state_path, {"state": state, "broker": self.broker_url, "created_at": datetime.now(timezone.utc).isoformat()})
        return f"{self.broker_url}/oauth/authorize?" + urlencode({"return_url": return_uri, "state": state})

    def complete_broker(self, code: str, state: str) -> dict[str, Any]:
        pending = self._load(self.state_path)
        if not pending or not secrets.compare_digest(str(pending.get("state", "")), state): raise ValueError("Broker authorization state is invalid or expired.")
        if datetime.now(timezone.utc) - datetime.fromisoformat(str(pending["created_at"])) > timedelta(minutes=10): raise ValueError("Broker authorization expired.")
        response = self._request_json(f"{pending['broker']}/oauth/token", json_body={"code": code})
        data = response.get("data", {}); token, accounts = data.get("token", {}), data.get("accounts", [])
        if not token.get("access_token") or not accounts: raise ValueError("Authorization broker returned no Cloudflare account.")
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600)))
        self._save(self.credentials_path, {"access_token":token["access_token"],"refresh_token":token.get("refresh_token", ""),"expires_at":expires.isoformat(),"account_id":str(accounts[0]["id"]),"accounts":accounts,"broker":pending["broker"]})
        self.state_path.unlink(missing_ok=True); return self.status()

    def complete(self, code: str, state: str) -> dict[str, Any]:
        pending = self._load(self.state_path)
        if not pending or not secrets.compare_digest(str(pending.get("state", "")), state):
            raise ValueError("Cloudflare authorization state is invalid or expired.")
        created = datetime.fromisoformat(str(pending["created_at"]))
        if datetime.now(timezone.utc) - created > timedelta(minutes=10):
            self.state_path.unlink(missing_ok=True)
            raise ValueError("Cloudflare authorization expired. Please connect again.")
        token = self._request_json(self.token_url, {"grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"], "client_id": self.client_id, "client_secret": self.client_secret, "code_verifier": pending["verifier"]})
        access_token = str(token.get("access_token", ""))
        if not access_token: raise ValueError("Cloudflare did not return an access token.")
        accounts_response = self._request_json(f"{self.api_url}/accounts?per_page=50", bearer=access_token)
        accounts = accounts_response.get("result", [])
        if not accounts: raise ValueError("No Cloudflare account was authorized.")
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600)))
        self._save(self.credentials_path, {"access_token": access_token, "refresh_token": token.get("refresh_token", ""), "expires_at": expires.isoformat(), "account_id": str(accounts[0]["id"]), "accounts": accounts})
        self.state_path.unlink(missing_ok=True)
        return self.status()

    def select_account(self, account_id: str) -> dict[str, Any]:
        credentials = self._load(self.credentials_path) or {}
        if account_id not in {str(item.get("id")) for item in credentials.get("accounts", [])}:
            raise ValueError("Select an account authorized by Cloudflare.")
        credentials["account_id"] = account_id
        self._save(self.credentials_path, credentials)
        return self.status()

    def deployment_credentials(self) -> tuple[str, str]:
        credentials = self._load(self.credentials_path) or {}
        if not credentials.get("access_token") or not credentials.get("account_id"):
            raise ValueError("Connect PHFrame to Cloudflare first.")
        expires = datetime.fromisoformat(str(credentials.get("expires_at")))
        if expires <= datetime.now(timezone.utc) + timedelta(minutes=2):
            refresh = str(credentials.get("refresh_token", ""))
            if not refresh: raise ValueError("Cloudflare authorization expired. Connect again.")
            if credentials.get("broker") and not self.client_secret:
                token = self._request_json(f"{credentials['broker']}/oauth/refresh", json_body={"refresh_token": refresh}).get("data", {}).get("token", {})
            else: token = self._request_json(self.token_url, {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": self.client_id, "client_secret": self.client_secret})
            credentials["access_token"] = token["access_token"]
            credentials["refresh_token"] = token.get("refresh_token", refresh)
            credentials["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600)))).isoformat()
            self._save(self.credentials_path, credentials)
        return str(credentials["account_id"]), str(credentials["access_token"])

    def disconnect(self) -> None:
        credentials = self._load(self.credentials_path) or {}
        token = str(credentials.get("access_token", ""))
        if token:
            try: self._request_json(self.revoke_url, {"token": token, "client_id": self.client_id, "client_secret": self.client_secret})
            except (ValueError, OSError): pass
        self.credentials_path.unlink(missing_ok=True)

    def _fernet(self) -> Fernet:
        configured = os.getenv("PHFRAME_CREDENTIAL_KEY", "").encode()
        if configured:
            try: return Fernet(configured)
            except (ValueError, TypeError) as error: raise ValueError("PHFRAME_CREDENTIAL_KEY must be a valid Fernet key.") from error
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists(): self.key_path.write_bytes(Fernet.generate_key()); self.key_path.chmod(0o600)
        return Fernet(self.key_path.read_bytes().strip())

    def _save(self, path: Path, value: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self._fernet().encrypt(json.dumps(value).encode())); path.chmod(0o600)

    def _load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists(): return None
        try: return json.loads(self._fernet().decrypt(path.read_bytes()))
        except (InvalidToken, json.JSONDecodeError) as error: raise ValueError("Stored Cloudflare credentials cannot be decrypted.") from error

    def _request_json(self, url: str, form: dict[str, Any] | None = None, bearer: str = "", json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(json_body).encode() if json_body is not None else (urlencode(form).encode() if form is not None else None)
        headers = {"accept": "application/json"}
        if form is not None: headers["content-type"] = "application/x-www-form-urlencoded"
        if json_body is not None: headers["content-type"] = "application/json"
        if bearer: headers["authorization"] = f"Bearer {bearer}"
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:  # nosec B310 - fixed Cloudflare origins
                result = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            detail = getattr(error, "reason", None) or str(error)
            raise ValueError(f"Cloudflare request failed: {detail}") from error
        if result.get("success") is False: raise ValueError("Cloudflare rejected the request: " + json.dumps(result.get("errors", [])))
        return result
