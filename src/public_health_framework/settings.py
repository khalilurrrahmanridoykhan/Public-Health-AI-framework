"""Runtime site branding and optional local authentication."""

from __future__ import annotations

import base64
from hashlib import pbkdf2_hmac
from html import escape
from html.parser import HTMLParser
import hmac
import json
from pathlib import Path
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_NAVIGATION = {
    "dashboard": {"label": "Dashboard", "visible": True},
    "records": {"label": "Records", "visible": True},
    "builder": {"label": "Data builder", "visible": True},
    "import": {"label": "Import", "visible": True},
    "connectors": {"label": "Connectors", "visible": True},
    "quality": {"label": "Data quality", "visible": True},
    "pages": {"label": "Pages", "visible": True},
    "ai": {"label": "AI assistance", "visible": False},
    "settings": {"label": "Settings", "visible": True},
}


class SiteSettings:
    def __init__(self, root: Path, project_name: str):
        self.root = root
        self.project_name = project_name
        self.data_dir = root / "data"
        self.path = self.data_dir / "phframe-settings.json"
        self.branding_dir = self.data_dir / "branding"
        self.boundary_dir = self.data_dir / "boundaries"

    def defaults(self) -> dict[str, Any]:
        return {
            "brand_name": "PHFrame",
            "header_title": self.project_name,
            "dashboard_title": "",
            "primary_color": "#087e8b",
            "default_theme": "light",
            "basemap": "carto-light",
            "logo_url": "/assets/phframe-logo.png",
            "favicon_url": "/assets/phframe-logo.png",
            "footer_html": 'Powered by PHFrame · Developed by <a href="https://krrkhan.com">Khalilur Rahman Ridoy Khan</a>',
            "show_footer": True,
            "navigation": DEFAULT_NAVIGATION,
            "pages": [],
            "dashboards": [],
            "ai_provider": "local",
            "ai_model": "phframe-evidence-v1",
            "ai_endpoint": "",
            "ai_api_key_env": "",
            "allow_external_ai": False,
            "access_mode": "public",
            "cloudflare_account_id": "",
            "cloudflare_project_name": "",
            "cloudflare_token_env": "CLOUDFLARE_API_TOKEN",
            "publications": [],
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
            "default_theme", "basemap", "footer_html", "show_footer", "navigation", "pages", "access_mode",
            "ai_provider", "ai_model", "ai_endpoint", "ai_api_key_env", "allow_external_ai",
            "dashboards", "cloudflare_account_id", "cloudflare_project_name", "cloudflare_token_env",
        }
        settings.update({key: value for key, value in values.items() if key in allowed})
        if settings["access_mode"] not in {"public", "private"}:
            raise ValueError("access_mode must be public or private.")
        if settings["default_theme"] not in {"light", "dark", "high-contrast"}:
            raise ValueError("default_theme is invalid.")
        if settings["basemap"] not in {"openstreetmap", "carto-light", "carto-dark", "esri-imagery"}:
            raise ValueError("basemap is invalid.")
        color = str(settings["primary_color"])
        if len(color) != 7 or not color.startswith("#") or any(char not in "0123456789abcdefABCDEF" for char in color[1:]):
            raise ValueError("primary_color must be a six-digit hex color.")
        settings["footer_html"] = sanitize_html(str(settings.get("footer_html", "")))
        settings["pages"] = self._validate_pages(settings.get("pages", []))
        settings["dashboards"] = self._validate_dashboards(settings.get("dashboards", []))
        if settings["ai_provider"] not in {"local", "openai_compatible"}:
            raise ValueError("ai_provider must be local or openai_compatible.")
        settings["ai_model"] = str(settings.get("ai_model", ""))[:255]
        settings["ai_endpoint"] = str(settings.get("ai_endpoint", ""))[:1000]
        settings["ai_api_key_env"] = str(settings.get("ai_api_key_env", ""))[:255]
        settings["cloudflare_account_id"] = str(settings.get("cloudflare_account_id", "")).strip()[:64]
        settings["cloudflare_project_name"] = str(settings.get("cloudflare_project_name", "")).strip().lower()[:58]
        settings["cloudflare_token_env"] = str(settings.get("cloudflare_token_env", "CLOUDFLARE_API_TOKEN")).strip()
        if settings["cloudflare_account_id"] and not re.fullmatch(r"[A-Za-z0-9_-]+", settings["cloudflare_account_id"]):
            raise ValueError("Cloudflare account ID contains invalid characters.")
        if settings["cloudflare_project_name"] and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", settings["cloudflare_project_name"]):
            raise ValueError("Cloudflare project name must use lowercase letters, numbers, and hyphens.")
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", settings["cloudflare_token_env"]):
            raise ValueError("Cloudflare token environment variable name is invalid.")
        if settings["ai_provider"] != "local" and settings.get("allow_external_ai"):
            if urlparse(settings["ai_endpoint"]).scheme != "https":
                raise ValueError("External AI endpoints must use HTTPS.")
            if not settings["ai_api_key_env"]:
                raise ValueError("External AI requires an API-key environment variable name.")
        if username or password:
            if not username or not password or len(password) < 10:
                raise ValueError("A username and password of at least 10 characters are required.")
            self._set_user(settings, username, password)
        if settings["access_mode"] == "private" and not settings.get("users"):
            raise ValueError("Create a login user before enabling private mode.")
        self._save(settings)
        return self.public()

    def record_publication(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = self.load()
        item = {
            "dashboard_id": str(values.get("dashboard_id", ""))[:200],
            "project_name": str(values.get("project_name", ""))[:100],
            "url": str(values.get("url", ""))[:1000],
            "mode": str(values.get("mode", "snapshot")),
            "refresh_minutes": int(values.get("refresh_minutes", 15)),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "privacy": values.get("privacy", {}),
        }
        if urlparse(item["url"]).scheme != "https" or item["mode"] not in {"snapshot", "live"}:
            raise ValueError("Publication record is invalid.")
        settings["publications"] = [item, *settings.get("publications", [])][:100]
        self._save(settings)
        return item

    def latest_publication(self, dashboard_id: str) -> dict[str, Any] | None:
        """Return the newest publication target remembered for a dashboard."""
        return next(
            (item for item in self.load().get("publications", []) if str(item.get("dashboard_id", "")) == dashboard_id),
            None,
        )

    def _validate_dashboards(self, dashboards: Any) -> list[dict[str, Any]]:
        if not isinstance(dashboards, list) or len(dashboards) > 50:
            raise ValueError("dashboards must contain at most 50 dashboards.")
        clean, ids = [], set()
        allowed_types = {"kpi", "field_kpi", "chart", "field_chart", "epi_curve", "map", "geo_map", "content"}
        for dashboard in dashboards:
            if not isinstance(dashboard, dict): raise ValueError("Each dashboard must be an object.")
            dashboard_id = str(dashboard.get("id", ""))
            if not dashboard_id or not dashboard_id.replace("-", "").isalnum() or dashboard_id in ids:
                raise ValueError("Dashboard IDs must be unique and contain letters, numbers, or hyphens.")
            ids.add(dashboard_id); widgets = dashboard.get("widgets", [])
            if not isinstance(widgets, list) or len(widgets) > 100: raise ValueError("A dashboard can contain at most 100 widgets.")
            clean_widgets = []
            for widget in widgets:
                if not isinstance(widget, dict) or widget.get("type") not in allowed_types: raise ValueError("Dashboard widget type is invalid.")
                item = {str(key): value for key, value in widget.items() if key in {"_id", "type", "title", "indicator", "dimension", "dataset", "field", "operation", "date_field", "value_field", "latitude_field", "longitude_field", "html"}}
                if item["type"] == "content": item["html"] = sanitize_html(str(item.get("html", "")))
                clean_widgets.append(item)
            clean.append({"id": dashboard_id, "title": str(dashboard.get("title", dashboard_id))[:200], "description": str(dashboard.get("description", ""))[:500], "dataset": str(dashboard.get("dataset", ""))[:255], "template": str(dashboard.get("template", "blank"))[:100], "widgets": clean_widgets})
        return clean

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

    def boundaries(self) -> list[dict[str, Any]]:
        if not self.boundary_dir.exists(): return []
        items = []
        for path in sorted(self.boundary_dir.glob("*.json")):
            if path.name == "countries.json": continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not data.get("id") or data.get("geojson", {}).get("type") != "FeatureCollection": continue
                items.append({key: data.get(key) for key in ("id", "country", "iso3", "level", "year", "source", "license", "feature_count")})
            except (OSError, json.JSONDecodeError, AttributeError): continue
        return items

    def boundary_countries(self) -> list[dict[str, str]]:
        cache = self.boundary_dir / "countries.json"
        if cache.exists():
            try: return json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): pass
        records = self._download_json("https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM0/", 2_000_000)
        if not isinstance(records, list): raise ValueError("Boundary provider returned an invalid country catalog.")
        countries = sorted(({"name": str(item.get("boundaryName", "")), "iso3": str(item.get("boundaryISO", "")).upper()} for item in records if re.fullmatch(r"[A-Z]{3}", str(item.get("boundaryISO", "")).upper())), key=lambda item: item["name"])
        self.boundary_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(countries), encoding="utf-8")
        return countries

    def boundary(self, boundary_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"[A-Z]{3}-ADM[0-5]", boundary_id): return None
        path = self.boundary_dir / f"{boundary_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def download_boundary(self, iso3: str, level: str) -> dict[str, Any]:
        iso3, level = iso3.strip().upper(), level.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", iso3) or not re.fullmatch(r"ADM[0-5]", level):
            raise ValueError("Use a three-letter ISO country code and ADM0–ADM5 level.")
        metadata_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/{level}/"
        metadata = self._download_json(metadata_url, 1_000_000)
        download_url = str(metadata.get("simplifiedGeometryGeoJSON") or metadata.get("gjDownloadURL") or "")
        if urlparse(download_url).scheme != "https": raise ValueError("Boundary provider returned an unsafe download URL.")
        geojson = self._download_json(download_url, 20_000_000)
        if geojson.get("type") != "FeatureCollection" or not isinstance(geojson.get("features"), list):
            raise ValueError("Boundary provider did not return valid GeoJSON.")
        boundary_id = f"{iso3}-{level}"
        stored = {"id": boundary_id, "country": metadata.get("boundaryName", iso3), "iso3": iso3, "level": level, "year": metadata.get("boundaryYearRepresented", ""), "source": "geoBoundaries gbOpen", "license": "CC BY 4.0", "feature_count": len(geojson["features"]), "geojson": geojson}
        self.boundary_dir.mkdir(parents=True, exist_ok=True)
        destination = self.boundary_dir / f"{boundary_id}.json"
        temporary = destination.with_suffix(".tmp"); temporary.write_text(json.dumps(stored), encoding="utf-8"); temporary.replace(destination)
        return {key: stored[key] for key in ("id", "country", "iso3", "level", "year", "source", "license", "feature_count")}

    @staticmethod
    def _download_json(url: str, maximum: int) -> Any:
        if urlparse(url).scheme != "https": raise ValueError("Download URL must use HTTPS.")
        request = Request(url, headers={"User-Agent": "PHFrame-boundary-manager/1", "Accept": "application/json"})
        with urlopen(request, timeout=30) as response:  # nosec B310 - HTTPS required above
            content = response.read(maximum + 1)
        if len(content) > maximum: raise ValueError("Boundary download is too large; choose a simplified or lower administrative level.")
        try: return json.loads(content)
        except json.JSONDecodeError as error: raise ValueError("Boundary provider returned invalid JSON.") from error

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
    allowed = {"a", "b", "strong", "em", "i", "u", "p", "br", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}

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
