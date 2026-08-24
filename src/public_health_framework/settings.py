"""Runtime site branding and optional local authentication."""

from __future__ import annotations

import base64
from hashlib import pbkdf2_hmac
from html import escape
from html.parser import HTMLParser
import hmac
import json
from pathlib import Path
import secrets
import time
from typing import Any
from urllib.parse import urlparse


DEFAULT_NAVIGATION = {
    "dashboard": {"label": "Dashboard", "visible": True},
    "records": {"label": "Records", "visible": True},
    "builder": {"label": "Data builder", "visible": True},
    "import": {"label": "Import", "visible": True},
    "connectors": {"label": "Connectors", "visible": True},
    "quality": {"label": "Data quality", "visible": True},
    "pages": {"label": "Pages", "visible": True},
    "settings": {"label": "Settings", "visible": True},
}


class SiteSettings:
    def __init__(self, root: Path, project_name: str):
        self.root = root
        self.project_name = project_name
        self.data_dir = root / "data"
        self.path = self.data_dir / "phframe-settings.json"
        self.branding_dir = self.data_dir / "branding"

    def defaults(self) -> dict[str, Any]:
        return {
            "brand_name": "PHFrame",
            "header_title": self.project_name,
            "dashboard_title": "",
            "primary_color": "#087e8b",
            "default_theme": "light",
            "logo_url": "/assets/phframe-logo.png",
            "favicon_url": "/assets/phframe-logo.png",
            "footer_html": 'Powered by PHFrame · Developed by <a href="https://krrkhan.com">Khalilur Rahman Ridoy Khan</a>',
            "show_footer": True,
            "navigation": DEFAULT_NAVIGATION,
            "pages": [],
            "access_mode": "public",
            "users": [],
        }

    def load(self) -> dict[str, Any]:
        settings = self.defaults()
        if self.path.exists():
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            if "footer_html" not in stored and "footer_text" in stored:
                stored["footer_html"] = f"<p>{escape(str(stored['footer_text']))}</p>"
            settings.update(stored)
            settings["navigation"] = {
                key: {**value, **stored.get("navigation", {}).get(key, {})}
                for key, value in DEFAULT_NAVIGATION.items()
            }
        return settings

    def public(self) -> dict[str, Any]:
        settings = self.load()
        settings.pop("users", None)
        settings["has_users"] = bool(self.load().get("users"))
        return settings

    def update(self, values: dict[str, Any], username: str = "", password: str = "") -> dict[str, Any]:
        settings = self.load()
        allowed = {
            "brand_name", "header_title", "dashboard_title", "primary_color",
            "default_theme", "footer_html", "show_footer", "navigation", "pages", "access_mode",
        }
        settings.update({key: value for key, value in values.items() if key in allowed})
        if settings["access_mode"] not in {"public", "private"}:
            raise ValueError("access_mode must be public or private.")
        if settings["default_theme"] not in {"light", "dark", "high-contrast"}:
            raise ValueError("default_theme is invalid.")
        color = str(settings["primary_color"])
        if len(color) != 7 or not color.startswith("#") or any(char not in "0123456789abcdefABCDEF" for char in color[1:]):
            raise ValueError("primary_color must be a six-digit hex color.")
        settings["footer_html"] = sanitize_html(str(settings.get("footer_html", "")))
        settings["pages"] = self._validate_pages(settings.get("pages", []))
        if username or password:
            if not username or not password or len(password) < 10:
                raise ValueError("A username and password of at least 10 characters are required.")
            self._set_user(settings, username, password)
        if settings["access_mode"] == "private" and not settings.get("users"):
            raise ValueError("Create a login user before enabling private mode.")
        self._save(settings)
        return self.public()

    def _validate_pages(self, pages: Any) -> list[dict[str, Any]]:
        if not isinstance(pages, list) or len(pages) > 50:
            raise ValueError("pages must be a list containing at most 50 pages.")
        clean: list[dict[str, Any]] = []
        slugs: set[str] = set()
        for page in pages:
            if not isinstance(page, dict):
                raise ValueError("Each page must be an object.")
            slug = str(page.get("slug", ""))
            if not slug or not slug.replace("-", "").isalnum() or slug in slugs:
                raise ValueError("Page slugs must be unique and contain letters, numbers, or hyphens.")
            slugs.add(slug)
            page_type = str(page.get("type", "internal"))
            if page_type not in {"internal", "external"}:
                raise ValueError("Page type must be internal or external.")
            url = str(page.get("url", ""))
            if page_type == "external" and urlparse(url).scheme not in {"http", "https"}:
                raise ValueError("External page URLs must use http or https.")
            blocks = page.get("blocks", []) if page_type == "internal" else []
            if not isinstance(blocks, list) or len(blocks) > 100:
                raise ValueError("A page can contain at most 100 blocks.")
            clean_blocks = []
            for block in blocks:
                if not isinstance(block, dict) or block.get("type") not in {"text", "table", "visualization"}:
                    raise ValueError("Page blocks must be text, table, or visualization blocks.")
                item = {str(key): value for key, value in block.items() if key in {"id", "type", "title", "html", "dataset", "source"}}
                if item["type"] == "text": item["html"] = sanitize_html(str(item.get("html", "")))
                clean_blocks.append(item)
            clean.append({"slug": slug, "title": str(page.get("title", slug))[:200], "nav_label": str(page.get("nav_label", page.get("title", slug)))[:100], "type": page_type, "url": url, "blocks": clean_blocks})
        return clean

    def _set_user(self, settings: dict[str, Any], username: str, password: str) -> None:
        username = username.strip()
        if not username or len(username) > 100:
            raise ValueError("Username is required and must be at most 100 characters.")
        salt = secrets.token_bytes(16)
        digest = pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
        user = {"username": username, "salt": base64.b64encode(salt).decode(), "password_hash": base64.b64encode(digest).decode()}
        settings["users"] = [item for item in settings.get("users", []) if item["username"] != username] + [user]

    def verify_password(self, username: str, password: str) -> bool:
        user = next((item for item in self.load().get("users", []) if item["username"] == username), None)
        if not user:
            return False
        expected = base64.b64decode(user["password_hash"])
        actual = pbkdf2_hmac("sha256", password.encode(), base64.b64decode(user["salt"]), 600_000)
        return hmac.compare_digest(expected, actual)

    def save_asset(self, kind: str, content: bytes, filename: str) -> str:
        if kind not in {"logo", "favicon"}:
            raise ValueError("Asset kind must be logo or favicon.")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".ico"}:
            raise ValueError("Brand images support PNG, JPG, WEBP, and ICO.")
        if not content or len(content) > 3 * 1024 * 1024:
            raise ValueError("Brand images must be between 1 byte and 3 MB.")
        self.branding_dir.mkdir(parents=True, exist_ok=True)
        destination = self.branding_dir / f"{kind}{suffix}"
        for existing in self.branding_dir.glob(f"{kind}.*"):
            if existing != destination:
                existing.unlink()
        destination.write_bytes(content)
        settings = self.load()
        settings[f"{kind}_url"] = f"/assets/project/{kind}"
        self._save(settings)
        return settings[f"{kind}_url"]

    def asset(self, kind: str) -> Path | None:
        matches = list(self.branding_dir.glob(f"{kind}.*")) if self.branding_dir.exists() else []
        return matches[0] if matches else None

    def token(self, username: str) -> str:
        payload = f"{username}:{int(time.time())}"
        signature = hmac.new(self._secret(), payload.encode(), "sha256").hexdigest()
        return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()

    def verify_token(self, token: str, max_age: int = 86400) -> str | None:
        try:
            username, timestamp, signature = base64.urlsafe_b64decode(token.encode()).decode().rsplit(":", 2)
            payload = f"{username}:{timestamp}"
            expected = hmac.new(self._secret(), payload.encode(), "sha256").hexdigest()
            if not hmac.compare_digest(expected, signature) or time.time() - int(timestamp) > max_age:
                return None
            return username
        except (ValueError, UnicodeDecodeError):
            return None

    def _secret(self) -> bytes:
        path = self.data_dir / ".phframe-secret"
        if not path.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(secrets.token_bytes(32))
        return path.read_bytes()

    def _save(self, settings: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class _SafeHTMLParser(HTMLParser):
    allowed = {"a", "b", "strong", "em", "i", "u", "p", "br", "ul", "ol", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.allowed: return
        clean = ""
        if tag == "a":
            href = next((value or "" for name, value in attrs if name == "href"), "")
            if urlparse(href).scheme in {"http", "https"}: clean = f' href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer"'
        self.parts.append(f"<{tag}{clean}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.allowed and tag != "br": self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))


def sanitize_html(value: str) -> str:
    parser = _SafeHTMLParser(); parser.feed(value); parser.close()
    return "".join(parser.parts)
