"""OAuth authorization-code connection for a DHIS2 instance."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken


class DHIS2OAuth:
    token_environment = "PHFRAME_DHIS2_OAUTH_TOKEN"
    username_environment = "PHFRAME_DHIS2_BASIC_USERNAME"
    password_environment = "PHFRAME_DHIS2_BASIC_PASSWORD"

    def __init__(self, root: Path):
        self.directory = Path(root) / "data"
        self.credentials_path = self.directory / ".dhis2-oauth"
        self.state_path = self.directory / ".dhis2-oauth-state"
        self.client_path = self.directory / ".dhis2-oauth-client"
        self.key_path = self.directory / ".credential-key"

    @property
    def client_id(self) -> str: return os.getenv("PHFRAME_DHIS2_CLIENT_ID", "").strip() or str((self._load(self.client_path) or {}).get("client_id", ""))

    @property
    def client_secret(self) -> str: return os.getenv("PHFRAME_DHIS2_CLIENT_SECRET", "").strip() or str((self._load(self.client_path) or {}).get("client_secret", ""))

    def configure_client(self, client_id: str, client_secret: str) -> None:
        if not client_id.strip() or not client_secret.strip(): raise ValueError("DHIS2 OAuth client ID and secret are required.")
        self._save(self.client_path, {"client_id": client_id.strip(), "client_secret": client_secret.strip()})

    def status(self) -> dict[str, Any]:
        credentials = self._load(self.credentials_path) or {}
        return {
            "available": bool(self.client_id and self.client_secret),
            "connected": bool(credentials.get("server_url") and (credentials.get("access_token") or credentials.get("username"))),
            "method": str(credentials.get("method", "oauth" if credentials.get("access_token") else "")),
            "server_url": str(credentials.get("server_url", "")),
            "user": credentials.get("user", {}),
            "expires_at": str(credentials.get("expires_at", "")),
        }

    def connect_password(self, server_url: str, username: str, password: str) -> dict[str, Any]:
        """Validate and encrypt a DHIS2 username/password connection."""
        server_url = self._server(server_url)
        username = username.strip()
        if not username or not password: raise ValueError("DHIS2 username and password are required.")
        user = self._request_json(server_url + "/api/me?fields=id,username,displayName", basic=(username, password))
        self._save(self.credentials_path, {"method": "password", "server_url": server_url, "username": username, "password": password, "user": user})
        return self.status()

    def basic_credentials(self, server_url: str = "") -> tuple[str, str]:
        credentials = self._load(self.credentials_path) or {}
        if credentials.get("method") != "password" or not credentials.get("username") or not credentials.get("password"):
            raise ValueError("Connect PHFrame to DHIS2 with a username and password first.")
        if server_url and self._server(server_url) != credentials.get("server_url"): raise ValueError("This connector uses a different DHIS2 server than the saved connection.")
        os.environ[self.username_environment] = str(credentials["username"])
        os.environ[self.password_environment] = str(credentials["password"])
        return str(credentials["username"]), str(credentials["password"])

    def begin(self, server_url: str, redirect_uri: str) -> str:
        server_url = self._server(server_url)
        if not self.client_id or not self.client_secret:
            raise ValueError("The PHFrame administrator must configure PHFRAME_DHIS2_CLIENT_ID and PHFRAME_DHIS2_CLIENT_SECRET.")
        state = secrets.token_urlsafe(32)
        self._save(self.state_path, {"state": state, "server_url": server_url, "redirect_uri": redirect_uri, "created_at": datetime.now(timezone.utc).isoformat()})
        authorize_path = os.getenv("PHFRAME_DHIS2_AUTHORIZE_PATH", "/uaa/oauth/authorize")
        return server_url + "/" + authorize_path.strip("/") + "?" + urlencode({"response_type": "code", "client_id": self.client_id, "redirect_uri": redirect_uri, "state": state})

    def complete(self, code: str, state: str) -> dict[str, Any]:
        pending = self._load(self.state_path)
        if not pending or not secrets.compare_digest(str(pending.get("state", "")), state):
            raise ValueError("DHIS2 authorization state is invalid or expired.")
        if datetime.now(timezone.utc) - datetime.fromisoformat(str(pending["created_at"])) > timedelta(minutes=10):
            self.state_path.unlink(missing_ok=True)
            raise ValueError("DHIS2 authorization expired. Connect again.")
        server_url = self._server(str(pending["server_url"])); token_path = os.getenv("PHFRAME_DHIS2_TOKEN_PATH", "/uaa/oauth/token")
        token = self._request_json(server_url + "/" + token_path.strip("/"), form={"grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"]}, basic=(self.client_id, self.client_secret))
        access_token = str(token.get("access_token", ""))
        if not access_token: raise ValueError("DHIS2 did not return an access token.")
        user = self._request_json(server_url + "/api/me?fields=id,username,displayName", bearer=access_token)
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 43200)))
        self._save(self.credentials_path, {"server_url": server_url, "access_token": access_token, "refresh_token": token.get("refresh_token", ""), "expires_at": expires.isoformat(), "user": user})
        self.state_path.unlink(missing_ok=True); os.environ[self.token_environment] = access_token
        return self.status()

    def access_token(self, server_url: str = "") -> str:
        credentials = self._load(self.credentials_path) or {}
        if not credentials.get("access_token"): raise ValueError("Connect PHFrame to DHIS2 first.")
        if server_url and self._server(server_url) != credentials.get("server_url"): raise ValueError("This connector uses a different DHIS2 server than the authorized connection.")
        expires = datetime.fromisoformat(str(credentials["expires_at"]))
        if expires <= datetime.now(timezone.utc) + timedelta(minutes=2):
            refresh = str(credentials.get("refresh_token", ""))
            if not refresh: raise ValueError("DHIS2 authorization expired. Connect again.")
            token_path = os.getenv("PHFRAME_DHIS2_TOKEN_PATH", "/uaa/oauth/token")
            token = self._request_json(str(credentials["server_url"]) + "/" + token_path.strip("/"), form={"grant_type": "refresh_token", "refresh_token": refresh}, basic=(self.client_id, self.client_secret))
            credentials["access_token"] = token["access_token"]; credentials["refresh_token"] = token.get("refresh_token", refresh)
            credentials["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 43200)))).isoformat(); self._save(self.credentials_path, credentials)
        os.environ[self.token_environment] = str(credentials["access_token"])
        return str(credentials["access_token"])

    def data_sets(self) -> list[dict[str, str]]:
        credentials = self._load(self.credentials_path) or {}
        if credentials.get("method") == "password":
            basic = self.basic_credentials(); result = self._request_json(str(credentials["server_url"]) + "/api/dataSets?fields=id,name,displayName&paging=false", basic=basic)
        else:
            token = self.access_token(); result = self._request_json(str(credentials["server_url"]) + "/api/dataSets?fields=id,name,displayName&paging=false", bearer=token)
        return [{"id": str(item.get("id", "")), "name": str(item.get("displayName") or item.get("name") or item.get("id", ""))} for item in result.get("dataSets", []) if item.get("id")]

    def data_set_sync_parameters(self, data_set_id: str) -> dict[str, str]:
        """Discover the root organisation unit and latest completed period."""
        credentials = self._load(self.credentials_path) or {}
        if not credentials.get("server_url"): raise ValueError("Connect PHFrame to DHIS2 first.")
        def get(path: str) -> dict[str, Any]:
            if credentials.get("method") == "password": return self._request_json(str(credentials["server_url"]) + path, basic=self.basic_credentials())
            return self._request_json(str(credentials["server_url"]) + path, bearer=self.access_token())
        units = get("/api/organisationUnits?filter=level:eq:1&fields=id,displayName&paging=false").get("organisationUnits", [])
        if not units or not units[0].get("id"): raise ValueError("DHIS2 has no accessible root organisation unit.")
        root = str(units[0]["id"])
        query = urlencode({"dataSet": data_set_id, "startDate": "2000-01-01", "endDate": date.today().isoformat(), "orgUnit": root, "children": "true", "limit": "1"})
        registrations = get("/api/completeDataSetRegistrations?" + query).get("completeDataSetRegistrations", [])
        if not registrations or not registrations[0].get("period"): raise ValueError("No completed reporting period is available for this DHIS2 dataset.")
        return {"period": str(registrations[0]["period"]), "orgUnit": root, "children": "true"}

    def disconnect(self) -> None:
        self.credentials_path.unlink(missing_ok=True)
        for name in (self.token_environment, self.username_environment, self.password_environment): os.environ.pop(name, None)

    def _server(self, value: str) -> str:
        parsed = urlparse(value.strip().rstrip("/"))
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}): raise ValueError("DHIS2 server URL must use HTTPS.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError("Enter a valid DHIS2 server base URL.")
        return value.strip().rstrip("/")

    def _fernet(self) -> Fernet:
        configured = os.getenv("PHFRAME_CREDENTIAL_KEY", "").encode()
        if configured:
            try: return Fernet(configured)
            except (ValueError, TypeError) as error: raise ValueError("PHFRAME_CREDENTIAL_KEY must be a valid Fernet key.") from error
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists(): self.key_path.write_bytes(Fernet.generate_key()); self.key_path.chmod(0o600)
        return Fernet(self.key_path.read_bytes().strip())

    def _save(self, path: Path, value: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True); path.write_bytes(self._fernet().encrypt(json.dumps(value).encode())); path.chmod(0o600)

    def _load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists(): return None
        try: return json.loads(self._fernet().decrypt(path.read_bytes()))
        except (InvalidToken, json.JSONDecodeError) as error: raise ValueError("Stored DHIS2 credentials cannot be decrypted.") from error

    def _request_json(self, url: str, form: dict[str, Any] | None = None, bearer: str = "", basic: tuple[str, str] | None = None) -> dict[str, Any]:
        data = urlencode(form).encode() if form is not None else None; headers = {"accept": "application/json"}
        if form is not None: headers["content-type"] = "application/x-www-form-urlencoded"
        if bearer: headers["authorization"] = f"Bearer {bearer}"
        if basic: headers["authorization"] = "Basic " + base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=30) as response: result = json.loads(response.read())  # nosec B310 - validated DHIS2 HTTPS server
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error: raise ValueError(f"DHIS2 request failed: {getattr(error, 'reason', None) or str(error)}") from error
        if not isinstance(result, dict): raise ValueError("DHIS2 returned an invalid response.")
        return result
