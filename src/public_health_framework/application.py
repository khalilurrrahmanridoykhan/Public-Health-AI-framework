"""PHFrame ASGI application and automatically generated dataset APIs."""

from __future__ import annotations

from html import escape
from http.cookies import SimpleCookie
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess  # nosec B404 - only fixed npx/wrangler argv lists are executed
import tempfile
from typing import Any
from urllib.request import Request as URLRequest, urlopen
from zipfile import ZipFile

import yaml

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware


_LEAFLET_CACHE: dict[str, bytes] = {}


def _leaflet_asset(name: str) -> bytes:
    """Serve pinned Leaflet assets through PHFrame so strict CSP remains self-only."""
    if name not in {"leaflet.css", "leaflet.js"}:
        raise ValueError("Unknown map asset.")
    if name not in _LEAFLET_CACHE:
        url = f"https://unpkg.com/leaflet@1.9.4/dist/{name}"
        with urlopen(URLRequest(url, headers={"User-Agent": "PHFrame/0.9"}), timeout=30) as response:  # nosec B310 fixed trusted origin
            _LEAFLET_CACHE[name] = response.read()
    return _LEAFLET_CACHE[name]

from . import __version__
from .config import ConnectorSchema, DatasetSchema, FIELD_TYPES, FieldSchema, ProjectConfig
from .plugins import load_plugins
from .periods import resolve_period
from .publishing import build_bundle, publication_audit, safe_project_name
from .importer import import_frame, load_uploaded_frame, preview_frame, stage_frame
from .storage import Storage
from .ui import asset_bytes, asset_text
from .settings import SiteSettings
from .sync import connector_due, sync_connector
from .ai import answer_question, deidentify_records, enrich_trend, evidence_digest, generate_summary
from .production import ProductionControls, validate_production_environment
from .cloudflare import CloudflareOAuth
from .dhis2_oauth import DHIS2OAuth
from .intelligence_quality import evaluate_quality
from .intelligence_repair import apply_repair, repair_proposals
from .intelligence_geo import infer_geography
from .intelligence_semantic import compile_semantic_model
from .intelligence_dashboard import generate_dashboard
from .intelligence_copilot import KNOWLEDGE_PACKS, match_knowledge_packs, propose_change
from .intelligence_assurance import assess_drift, evaluate_assurance


class PHFrame:
    """A public-health application created from a PHFrame project configuration."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.storage = Storage(config)
        self.storage.initialize()
        self.site_settings = SiteSettings(config.root, config.name)
        self.production = ProductionControls(config.root)
        self.cloudflare = CloudflareOAuth(config.root)
        self.dhis2_oauth = DHIS2OAuth(config.root)
        routes = [
            Route("/", self.home, methods=["GET"]),
            Route("/app", self.frontend, methods=["GET"]),
            Route("/assets/phframe.css", self.frontend_css, methods=["GET"]),
            Route("/assets/phframe.js", self.frontend_js, methods=["GET"]),
            Route("/assets/leaflet.css", self.leaflet_css, methods=["GET"]),
            Route("/assets/leaflet.js", self.leaflet_js, methods=["GET"]),
            Route("/assets/phframe-logo.png", self.framework_logo, methods=["GET"]),
            Route("/assets/project/{kind}", self.project_asset, methods=["GET"]),
            Route("/login", self.login_page, methods=["GET"]),
            Route("/health", self.health, methods=["GET"]),
            Route("/ready", self.ready, methods=["GET"]),
            Route("/api/operations/audit", self.operations_audit, methods=["GET"]),
            Route("/api/auth/status", self.auth_status, methods=["GET"]),
            Route("/api/auth/login", self.auth_login, methods=["POST"]),
            Route("/api/auth/logout", self.auth_logout, methods=["POST"]),
            Route("/api/settings", self.settings_api, methods=["GET", "PUT"]),
            Route("/api/settings/assets/{kind}", self.settings_asset_upload, methods=["POST"]),
            Route("/api/boundaries", self.boundary_index, methods=["GET", "POST"]),
            Route("/api/boundaries/countries", self.boundary_countries, methods=["GET"]),
            Route("/api/boundaries/{boundary_id}", self.boundary_detail, methods=["GET"]),
            Route("/api/publications", self.publication_index, methods=["GET"]),
            Route("/api/publications/feed/{dashboard_id}", self.publication_feed, methods=["GET"]),
            Route("/api/publications/preview", self.publication_preview, methods=["POST"]),
            Route("/api/publications/bundle", self.publication_bundle, methods=["POST"]),
            Route("/api/publications/deploy", self.publication_deploy, methods=["POST"]),
            Route("/api/integrations/cloudflare/status", self.cloudflare_status, methods=["GET"]),
            Route("/api/integrations/cloudflare/connect", self.cloudflare_connect, methods=["GET"]),
            Route("/api/integrations/cloudflare/callback", self.cloudflare_callback, methods=["GET"]),
            Route("/api/integrations/cloudflare/broker/callback", self.cloudflare_broker_callback, methods=["GET"]),
            Route("/api/integrations/cloudflare/account", self.cloudflare_account, methods=["PUT"]),
            Route("/api/integrations/cloudflare/disconnect", self.cloudflare_disconnect, methods=["POST"]),
            Route("/api/integrations/dhis2/status", self.dhis2_status, methods=["GET"]),
            Route("/api/integrations/dhis2/connect", self.dhis2_connect, methods=["GET"]),
            Route("/api/integrations/dhis2/password-connect", self.dhis2_password_connect, methods=["POST"]),
            Route("/api/integrations/dhis2/callback", self.dhis2_callback, methods=["GET"]),
            Route("/api/integrations/dhis2/data-sets", self.dhis2_data_sets, methods=["GET"]),
            Route("/api/integrations/dhis2/import-data-set", self.dhis2_import_data_set, methods=["POST"]),
            Route("/api/integrations/dhis2/disconnect", self.dhis2_disconnect, methods=["POST"]),
            Route("/api/ai/deidentify/{dataset}", self.ai_deidentify, methods=["POST"]),
            Route("/api/ai/chat", self.ai_chat, methods=["GET", "POST"]),
            Route("/api/ai/chat/{chat_id:int}/report", self.ai_chat_report, methods=["POST"]),
            Route("/api/ai/summaries", self.ai_summaries, methods=["GET", "POST"]),
            Route("/api/ai/summaries/{summary_id:int}", self.ai_summary_detail, methods=["GET"]),
            Route("/api/ai/summaries/{summary_id:int}/export", self.ai_summary_export, methods=["GET"]),
            Route("/api/ai/summaries/{summary_id:int}/review", self.ai_summary_review, methods=["POST"]),
            Route("/api/ai/audit", self.ai_audit, methods=["GET"]),
            Route("/api", self.api_index, methods=["GET"]),
            Route("/api/imports", self.import_history, methods=["GET"]),
            Route("/api/imports/{run_id:int}/errors", self.import_errors, methods=["GET"]),
            Route("/api/staging", self.staging_index, methods=["GET"]),
            Route("/api/staging/{version_id:int}", self.staging_detail, methods=["GET", "PATCH"]),
            Route("/api/staging/{version_id:int}/rows", self.staging_rows, methods=["GET"]),
            Route("/api/staging/{version_id:int}/quality", self.staging_quality, methods=["GET", "POST"]),
            Route("/api/staging/{version_id:int}/repairs", self.staging_repairs, methods=["GET", "POST"]),
            Route("/api/transformations", self.transformation_index, methods=["GET"]),
            Route("/api/staging/{version_id:int}/geography", self.staging_geography, methods=["GET", "POST"]),
            Route("/api/staging/{version_id:int}/semantic", self.staging_semantic, methods=["GET", "POST", "PATCH"]),
            Route("/api/staging/{version_id:int}/dashboards", self.staging_dashboards, methods=["GET", "POST"]),
            Route("/api/staging/{version_id:int}/dashboards/{dashboard_id:int}", self.staging_dashboard_detail, methods=["PATCH"]),
            Route("/api/intelligence/knowledge-packs", self.intelligence_knowledge_packs, methods=["GET"]),
            Route("/api/staging/{version_id:int}/assistant", self.staging_assistant, methods=["POST"]),
            Route("/api/staging/{version_id:int}/assurance", self.staging_assurance, methods=["GET", "POST"]),
            Route("/api/import-mappings", self.import_mapping_index, methods=["GET"]),
            Route("/api/import-mappings/{name}", self.import_mapping_save, methods=["PUT"]),
            Route("/api/browser-import/{dataset}/preview", self.browser_import_preview, methods=["POST"]),
            Route("/api/browser-import/{dataset}", self.browser_import, methods=["POST"]),
            Route("/api/import-example/{dataset}", self.import_example, methods=["GET"]),
            Route("/api/project/datasets/{dataset}/fields", self.dataset_field_create, methods=["POST"]),
            Route("/api/indicators", self.indicator_index, methods=["GET"]),
            Route("/api/indicators/{indicator}", self.indicator_result, methods=["GET"]),
            Route("/api/data-quality", self.data_quality_index, methods=["GET"]),
            Route("/api/data-quality/{rule}", self.data_quality_result, methods=["GET"]),
            Route("/api/filters", self.filter_index, methods=["GET"]),
            Route("/api/dimensions", self.dimension_index, methods=["GET"]),
            Route("/api/dimensions/{dimension}", self.dimension_result, methods=["GET"]),
            Route("/api/thresholds", self.threshold_index, methods=["GET"]),
            Route("/api/thresholds/{threshold}", self.threshold_result, methods=["GET"]),
            Route("/api/organisation-units", self.organisation_unit_index, methods=["GET"]),
            Route("/api/organisation-units/{code}", self.organisation_unit_detail, methods=["GET"]),
            Route("/api/dashboards/{dashboard}", self.dashboard, methods=["GET"]),
            Route("/api/epi-curve/{dataset}", self.epi_curve, methods=["GET"]),
            Route("/api/visualize/{dataset}", self.visualize_field, methods=["GET"]),
            Route("/api/geospatial/{dataset}", self.geospatial, methods=["GET"]),
            Route("/api/connectors", self.connector_index, methods=["GET", "POST"]),
            Route("/api/connectors/{connector}/sync", self.connector_sync, methods=["POST"]),
            Route("/api/connectors/{connector}", self.connector_delete, methods=["DELETE"]),
            Route("/api/syncs", self.sync_history, methods=["GET"]),
            Route("/api/{dataset}", self.collection, methods=["GET", "POST"]),
            Route("/api/{dataset}/{record_id:int}", self.detail, methods=["GET", "PUT", "PATCH", "DELETE"]),
        ]
        self.asgi = Starlette(debug=False, routes=routes)
        self.asgi.add_middleware(GZipMiddleware, minimum_size=800)
        self.asgi.state.phframe = self
        load_plugins(config.plugins, self.asgi, config)

    @classmethod
    def from_file(cls, path: str = "phframe.yaml") -> "PHFrame":
        return cls(ProjectConfig.load(path))

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and not self._authorized_scope(scope):
            path = scope.get("path", "")
            response: Response = JSONResponse({"error": {"message": "Authentication required."}}, status_code=401) if path == "/api" or path.startswith("/api/") else RedirectResponse("/login", status_code=303)
            await response(scope, receive, send)
            return
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        actor = "api-token" if headers.get("authorization", "").startswith("Bearer ") else "session"
        await self.production.serve(self.asgi, scope, receive, send, actor)

    def _authorized_scope(self, scope: dict[str, Any]) -> bool:
        settings = self.site_settings.load()
        path = scope.get("path", "")
        if path == "/login" or path == "/health" or path.startswith("/assets/") or path in {"/api/auth/login", "/api/auth/logout", "/api/auth/status"}:
            return True
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        api_token = os.getenv("PHFRAME_API_TOKEN", "")
        if path.startswith("/api/") and scope.get("method") not in {"GET", "HEAD", "OPTIONS"} and api_token:
            supplied = headers.get("authorization", "").removeprefix("Bearer ")
            if secrets.compare_digest(supplied, api_token): return True
        if settings["access_mode"] == "public": return True
        cookie = SimpleCookie(); cookie.load(headers.get("cookie", ""))
        token = cookie.get("phframe_session")
        return bool(token and self.site_settings.verify_token(token.value))

    async def home(self, request: Request) -> HTMLResponse:
        datasets = "".join(
            f'<li><a href="/api/{escape(dataset.name)}">{escape(dataset.label)}</a>'
            f" <code>/api/{escape(dataset.name)}</code></li>"
            for dataset in self.config.datasets.values()
        ) or "<li>No datasets configured.</li>"
        html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(self.config.name)}</title>
<style>body{{font:16px/1.5 system-ui;max-width:820px;margin:60px auto;padding:0 24px;color:#17313d}}
code{{background:#e8f3f2;padding:3px 6px;border-radius:5px}}a{{color:#087e8b}}.mark{{color:#087e8b}}</style></head>
<body><h1><span class="mark">PHFrame</span> · {escape(self.config.name)}</h1>
<p>Your public-health application is running.</p><h2>Datasets</h2><ul>{datasets}</ul>
<p><a href="/app">Open application</a> · <a href="/api">API metadata</a> · <a href="/health">Health check</a></p></body></html>"""
        return HTMLResponse(html)

    async def health(self, request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "framework": "PHFrame", "version": __version__, "project": self.config.name})

    async def ready(self, request: Request) -> JSONResponse:
        try: self.storage.initialize(); issues = validate_production_environment(self.config)
        except Exception as error: return JSONResponse({"status": "not-ready", "error": str(error)}, status_code=503)
        return JSONResponse({"status": "ready" if not issues else "warning", "database": "ready", "issues": issues}, status_code=200)

    async def operations_audit(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": self.production.history(int(request.query_params.get("limit", "100")))})

    async def frontend(self, request: Request) -> HTMLResponse:
        return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PHFrame</title>
<link rel="icon" href="/assets/phframe-logo.png" data-ph-favicon>
<link rel="stylesheet" href="/assets/phframe.css"></head><body><ph-app-shell></ph-app-shell>
<noscript>PHFrame requires JavaScript for the application interface. Dataset APIs remain available at /api.</noscript>
<script type="module" src="/assets/phframe.js"></script></body></html>""")

    async def frontend_css(self, request: Request) -> Response:
        return Response(asset_text("phframe.css"), media_type="text/css", headers={"cache-control": "public, max-age=3600"})

    async def frontend_js(self, request: Request) -> Response:
        return Response(asset_text("phframe.js"), media_type="text/javascript", headers={"cache-control": "public, max-age=3600"})

    async def leaflet_css(self, request: Request) -> Response:
        return Response(_leaflet_asset("leaflet.css"), media_type="text/css", headers={"cache-control": "public, max-age=86400"})

    async def leaflet_js(self, request: Request) -> Response:
        return Response(_leaflet_asset("leaflet.js"), media_type="text/javascript", headers={"cache-control": "public, max-age=86400"})

    async def framework_logo(self, request: Request) -> Response:
        return Response(asset_bytes("phframe-logo.png"), media_type="image/png", headers={"cache-control": "public, max-age=86400"})

    async def project_asset(self, request: Request) -> Response:
        path = self.site_settings.asset(request.path_params["kind"])
        if not path:
            return _error("Brand asset not found.", 404)
        return Response(path.read_bytes(), media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", headers={"cache-control": "no-cache"})

    async def login_page(self, request: Request) -> HTMLResponse:
        settings = self.site_settings.public()
        return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · {escape(settings['brand_name'])}</title><link rel="icon" href="{escape(settings['favicon_url'])}"><link rel="stylesheet" href="/assets/phframe.css"></head><body class="ph-login-page"><main class="ph-login-card"><img src="{escape(settings['logo_url'])}" alt=""><p class="ph-eyebrow">{escape(settings['brand_name'])}</p><h1>Welcome back</h1><p class="ph-muted">Sign in to access {escape(settings['header_title'])}.</p><form class="ph-stack"><div class="ph-field"><label>Username<input name="username" autocomplete="username" required></label></div><div class="ph-field"><label>Password<input name="password" type="password" autocomplete="current-password" required></label></div><button class="ph-button">Sign in</button><p role="alert" class="ph-error"></p></form></main><script>document.querySelector('form').addEventListener('submit',async e=>{{e.preventDefault();const r=await fetch('/api/auth/login',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}});if(r.ok)location.href='/app';else document.querySelector('[role=alert]').textContent='Invalid username or password.'}})</script></body></html>""")

    async def auth_status(self, request: Request) -> JSONResponse:
        settings = self.site_settings.public()
        cookie = request.cookies.get("phframe_session", "")
        return JSONResponse({"data": {"access_mode": settings["access_mode"], "authenticated": bool(self.site_settings.verify_token(cookie))}})

    async def auth_login(self, request: Request) -> Response:
        try:
            payload = await request.json()
            username, password = str(payload.get("username", "")), str(payload.get("password", ""))
        except (json.JSONDecodeError, AttributeError):
            return _error("Invalid login request.", 400)
        if not self.site_settings.verify_password(username, password):
            return _error("Invalid username or password.", 401)
        response = JSONResponse({"data": {"authenticated": True, "username": username}})
        response.set_cookie("phframe_session", self.site_settings.token(username), max_age=86400, httponly=True, samesite="lax", secure=request.url.scheme == "https")
        return response

    async def auth_logout(self, request: Request) -> Response:
        response = JSONResponse({"data": {"authenticated": False}})
        response.delete_cookie("phframe_session")
        return response

    async def settings_api(self, request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse({"data": self.site_settings.public()})
        try:
            payload = await request.json()
            username = str(payload.pop("username", "")); password = str(payload.pop("password", ""))
            return JSONResponse({"data": self.site_settings.update(payload, username, password)})
        except (TypeError, ValueError) as error:
            return _error(str(error), 422)

    async def settings_asset_upload(self, request: Request) -> Response:
        filename = request.query_params.get("filename", "")
        try:
            url = self.site_settings.save_asset(request.path_params["kind"], await request.body(), filename)
            return JSONResponse({"data": {"url": url}})
        except ValueError as error:
            return _error(str(error), 422)

    async def boundary_index(self, request: Request) -> Response:
        if request.method == "GET": return JSONResponse({"data": self.site_settings.boundaries()})
        try:
            payload = await request.json()
            item = await run_in_threadpool(self.site_settings.download_boundary, str(payload.get("iso3", "")), str(payload.get("level", "")))
            return JSONResponse({"data": item}, status_code=201)
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as error:
            return _error(str(error), 422)

    async def boundary_detail(self, request: Request) -> Response:
        item = self.site_settings.boundary(request.path_params["boundary_id"])
        if not item: return _error("Boundary layer not found.", 404)
        return JSONResponse({"data": item})

    async def boundary_countries(self, request: Request) -> Response:
        try: return JSONResponse({"data": await run_in_threadpool(self.site_settings.boundary_countries)})
        except (ValueError, OSError) as error: return _error(str(error), 502)

    async def publication_index(self, request: Request) -> Response:
        settings = self.site_settings.load()
        status = self.cloudflare.status()
        return JSONResponse({"data": settings.get("publications", []), "cloudflare": {"configured": status["connected"] or bool(os.getenv(settings.get("cloudflare_token_env", "CLOUDFLARE_API_TOKEN")) and settings.get("cloudflare_account_id")), "oauth": status}})

    async def cloudflare_status(self, request: Request) -> Response:
        return JSONResponse({"data": self.cloudflare.status()})

    async def cloudflare_connect(self, request: Request) -> Response:
        try:
            redirect_uri = os.getenv("PHFRAME_CLOUDFLARE_REDIRECT_URI", str(request.url_for("cloudflare_callback")))
            return RedirectResponse(self.cloudflare.begin(redirect_uri), status_code=303)
        except ValueError as error: return _error(str(error), 503)

    async def cloudflare_callback(self, request: Request) -> Response:
        if request.query_params.get("error"):
            return RedirectResponse("/app#/settings?cloudflare=denied", status_code=303)
        try:
            self.cloudflare.complete(str(request.query_params.get("code", "")), str(request.query_params.get("state", "")))
            return RedirectResponse("/app#/settings?cloudflare=connected", status_code=303)
        except ValueError:
            return RedirectResponse("/app#/settings?cloudflare=failed", status_code=303)

    async def cloudflare_broker_callback(self, request: Request) -> Response:
        try:
            self.cloudflare.complete_broker(str(request.query_params.get("broker_code", "")), str(request.query_params.get("state", "")))
            return RedirectResponse("/app#/settings?cloudflare=connected", status_code=303)
        except ValueError: return RedirectResponse("/app#/settings?cloudflare=failed", status_code=303)

    async def cloudflare_account(self, request: Request) -> Response:
        try: return JSONResponse({"data": self.cloudflare.select_account(str((await request.json()).get("account_id", "")))})
        except (json.JSONDecodeError, AttributeError, ValueError) as error: return _error(str(error), 422)

    async def cloudflare_disconnect(self, request: Request) -> Response:
        self.cloudflare.disconnect()
        return JSONResponse({"data": self.cloudflare.status()})

    async def dhis2_status(self, request: Request) -> Response:
        return JSONResponse({"data": self.dhis2_oauth.status()})

    async def dhis2_connect(self, request: Request) -> Response:
        try:
            redirect_uri = os.getenv("PHFRAME_DHIS2_REDIRECT_URI", str(request.url_for("dhis2_callback")))
            return RedirectResponse(self.dhis2_oauth.begin(str(request.query_params.get("server_url", "")), redirect_uri), status_code=303)
        except ValueError as error: return _error(str(error), 503)

    async def dhis2_password_connect(self, request: Request) -> Response:
        try:
            payload = await request.json()
            status = await run_in_threadpool(self.dhis2_oauth.connect_password, str(payload.get("server_url", "")), str(payload.get("username", "")), str(payload.get("password", "")))
            return JSONResponse({"data": status})
        except (json.JSONDecodeError, AttributeError, ValueError) as error: return _error(str(error), 422)

    async def dhis2_callback(self, request: Request) -> Response:
        if request.query_params.get("error"): return RedirectResponse("/app#/connectors?dhis2=denied", status_code=303)
        try:
            self.dhis2_oauth.complete(str(request.query_params.get("code", "")), str(request.query_params.get("state", "")))
            return RedirectResponse("/app#/connectors?dhis2=connected", status_code=303)
        except ValueError: return RedirectResponse("/app#/connectors?dhis2=failed", status_code=303)

    async def dhis2_data_sets(self, request: Request) -> Response:
        try: return JSONResponse({"data": await run_in_threadpool(self.dhis2_oauth.data_sets)})
        except ValueError as error: return _error(str(error), 502)

    async def dhis2_import_data_set(self, request: Request) -> Response:
        try:
            payload = await request.json(); remote_id = str(payload.get("data_set_id", "")).strip(); remote_name = str(payload.get("data_set_name", remote_id)).strip()
            local_name = re.sub(r"[^a-z0-9_]+", "_", str(payload.get("local_name", "")).strip().lower()).strip("_")
            if not remote_id: raise ValueError("Select a DHIS2 data set.")
            if not re.fullmatch(r"[a-z][a-z0-9_]*", local_name): raise ValueError("New dataset name must begin with a letter and use lowercase letters, numbers, and underscores.")
            if local_name in self.config.datasets: raise ValueError(f"Dataset already exists: {local_name}")
            connector_name = f"{local_name}_dhis2"; schedule = int(payload.get("schedule_minutes", 60))
            fields = {
                "data_element": {"type": "identifier", "label": "Data element"}, "period": {"type": "reporting_period", "label": "Period"},
                "org_unit": {"type": "identifier", "label": "DHIS2 organisation unit UID"}, "category_option_combo": {"type": "string", "label": "Category option combination"},
                "attribute_option_combo": {"type": "string", "label": "Attribute option combination"}, "value": {"type": "string", "label": "Value"},
                "stored_by": {"type": "string", "label": "Stored by"}, "created": {"type": "datetime", "label": "Created"},
                "last_updated": {"type": "datetime", "label": "Last updated"}, "comment": {"type": "string", "label": "Comment"},
                "follow_up": {"type": "boolean", "label": "Follow up"},
            }
            mapping = {"dataElement": "data_element", "period": "period", "orgUnit": "org_unit", "categoryOptionCombo": "category_option_combo", "attributeOptionCombo": "attribute_option_combo", "value": "value", "storedBy": "stored_by", "created": "created", "lastUpdated": "last_updated", "comment": "comment", "followUp": "follow_up"}
            parameters = await run_in_threadpool(self.dhis2_oauth.data_set_sync_parameters, remote_id)
            dataset_value = {"label": remote_name or local_name.replace("_", " ").title(), "fields": fields}
            connection = self.dhis2_oauth.status()
            auth = ({"username_env": DHIS2OAuth.username_environment, "password_env": DHIS2OAuth.password_environment} if connection.get("method") == "password" else {"token_env": DHIS2OAuth.token_environment})
            connector_value = {"type": "dhis2", "dataset": local_name, "base_url": connection["server_url"], "resource": remote_id, "parameters": parameters, "mapping": mapping, "schedule_minutes": schedule, "auth": auth}
            dataset = DatasetSchema.from_dict(local_name, dataset_value); connector = ConnectorSchema.from_dict(connector_name, connector_value, {**self.config.datasets, local_name: dataset})
            self._update_config_many({"datasets": {local_name: dataset_value}, "connectors": {connector_name: connector_value}})
            self.config.datasets[local_name] = dataset; self.config.connectors[connector_name] = connector
            self.storage = Storage(self.config); self.storage.initialize()
            return JSONResponse({"data": {"dataset": local_name, "label": dataset.label, "connector": self._connector_data(connector)}}, status_code=201)
        except (json.JSONDecodeError, TypeError, ValueError) as error: return _error(str(error), 422)

    async def dhis2_disconnect(self, request: Request) -> Response:
        self.dhis2_oauth.disconnect(); return JSONResponse({"data": self.dhis2_oauth.status()})

    async def publication_feed(self, request: Request) -> Response:
        try:
            dashboard = self._publication_dashboard(request.path_params["dashboard_id"])
            audit = publication_audit(self.config, dashboard, "snapshot")
            if not audit["approved"]: raise ValueError("Privacy review failed: " + "; ".join(audit["findings"]))
            return JSONResponse(self._publication_snapshot(dashboard), headers={"cache-control": "public, max-age=60"})
        except ValueError as error: return _error(str(error), 422)

    def _publication_dashboard(self, dashboard_id: str) -> dict[str, Any]:
        if dashboard_id.startswith("configured-"):
            name = dashboard_id.removeprefix("configured-"); dashboard = self.config.dashboards.get(name)
            if not dashboard: raise ValueError("Dashboard not found.")
            return {"id": dashboard_id, "title": dashboard.label, "widgets": [{key: value for key, value in vars(widget).items() if value is not None} for widget in dashboard.widgets]}
        dashboard = next((item for item in self.site_settings.load().get("dashboards", []) if item.get("id") == dashboard_id), None)
        if not dashboard: raise ValueError("Dashboard not found.")
        return dashboard

    def _publication_snapshot(self, dashboard: dict[str, Any]) -> dict[str, Any]:
        widgets = []
        boundary_layers = self.site_settings.boundaries()
        boundary = self.site_settings.boundary(str(boundary_layers[-1]["id"])) if boundary_layers else None
        for widget in dashboard.get("widgets", []):
            kind, result = widget.get("type"), {"type": widget.get("type"), "title": widget.get("title", widget.get("type", "Widget"))}
            if kind == "content": result["html"] = widget.get("html", "")
            elif kind == "kpi" and widget.get("indicator") in self.config.indicators:
                result.update(self.storage.indicator(self.config.indicators[widget["indicator"]]))
            elif kind in {"chart", "map"} and widget.get("dimension") in self.config.dimensions:
                result.update(self.storage.dimension(self.config.dimensions[widget["dimension"]]))
                if kind == "map" and boundary:
                    result["boundary"] = {key: boundary.get(key) for key in ("country", "level", "source", "license")}
                    result["geojson"] = boundary.get("geojson")
            elif kind in {"field_kpi", "field_chart"} and widget.get("dataset") in self.config.datasets:
                records = self.storage.list(self.config.datasets[widget["dataset"]], limit=1000); field = widget.get("field")
                if kind == "field_kpi":
                    numbers = [float(row[field]) for row in records if row.get(field) is not None]; operation = widget.get("operation", "sum"); result.update({"value": len(numbers) if operation == "count" else (sum(numbers) if operation == "sum" else (sum(numbers) / len(numbers) if numbers else None)), "operation": operation})
                else:
                    counts = {}; [counts.__setitem__(str(row.get(field) or "Unknown"), counts.get(str(row.get(field) or "Unknown"), 0) + 1) for row in records]; result["values"] = [{"value": key, "count": value} for key, value in sorted(counts.items(), key=lambda item: -item[1])]
            elif kind == "epi_curve" and widget.get("dataset") in self.config.datasets:
                result["values"] = self.storage.epi_curve(self.config.datasets[widget["dataset"]], widget.get("date_field", ""), widget.get("value_field"))
            elif kind == "geo_map" and widget.get("dataset") in self.config.datasets:
                dataset = self.config.datasets[widget["dataset"]]; lat, lon, buckets = widget.get("latitude_field"), widget.get("longitude_field"), {}
                for row in self.storage.list(dataset, limit=1000):
                    if row.get(lat) is None or row.get(lon) is None: continue
                    point = (round(float(row[lat]), 2), round(float(row[lon]), 2)); buckets[point] = buckets.get(point, 0) + 1
                result["values"] = [{"latitude": point[0], "longitude": point[1], "count": count} for point, count in buckets.items()]
            widgets.append(result)
        return {"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "widgets": widgets}

    def _publication_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str, int]:
        dashboard = self._publication_dashboard(str(payload.get("dashboard_id", ""))); mode = str(payload.get("mode", "snapshot")); upstream = str(payload.get("upstream_url", "")); refresh = max(1, min(int(payload.get("refresh_minutes", 15)), 1440)); audit = publication_audit(self.config, dashboard, mode, upstream)
        if not audit["approved"]: raise ValueError("Privacy review failed: " + "; ".join(audit["findings"]))
        return dashboard, audit, mode, upstream, refresh

    async def publication_preview(self, request: Request) -> Response:
        try:
            _, audit, _, _, _ = self._publication_payload(await request.json()); return JSONResponse({"data": audit})
        except (json.JSONDecodeError, TypeError, ValueError) as error: return _error(str(error), 422)

    async def publication_bundle(self, request: Request) -> Response:
        try:
            dashboard, _, mode, upstream, refresh = self._publication_payload(await request.json()); content = build_bundle(dashboard, self._publication_snapshot(dashboard), self.site_settings.public(), mode, upstream, refresh)
            return Response(content, media_type="application/zip", headers={"content-disposition": f'attachment; filename="{safe_project_name(dashboard.get("title", "dashboard"))}-cloudflare.zip"'})
        except (json.JSONDecodeError, TypeError, ValueError) as error: return _error(str(error), 422)

    async def publication_deploy(self, request: Request) -> Response:
        try:
            payload = await request.json(); dashboard, audit, mode, upstream, refresh = self._publication_payload(payload); settings = self.site_settings.load(); previous = self.site_settings.latest_publication(str(dashboard.get("id", ""))) or {}; project = safe_project_name(str(payload.get("project_name") or previous.get("project_name") or settings.get("cloudflare_project_name") or dashboard.get("title")))
            try: account, token = self.cloudflare.deployment_credentials()
            except ValueError:
                account = str(settings.get("cloudflare_account_id", "")); token_env = str(settings.get("cloudflare_token_env", "CLOUDFLARE_API_TOKEN")); token = os.getenv(token_env, "")
                if not account or not token: raise ValueError(f"Connect PHFrame to Cloudflare first, or set the advanced {token_env} API-token fallback.")
            content = build_bundle(dashboard, self._publication_snapshot(dashboard), self.site_settings.public(), mode, upstream, refresh)
            with tempfile.TemporaryDirectory(prefix="phframe-publish-") as directory:
                archive_path = Path(directory) / "bundle.zip"; archive_path.write_bytes(content)
                with ZipFile(archive_path) as archive: archive.extractall(Path(directory) / "site")
                environment = {**os.environ, "CLOUDFLARE_ACCOUNT_ID": account, "CLOUDFLARE_API_TOKEN": token}
                await run_in_threadpool(self.cloudflare.ensure_pages_project, account, token, project)
                process = await run_in_threadpool(subprocess.run, ["npx", "--yes", "wrangler", "pages", "deploy", str(Path(directory) / "site"), "--project-name", project, "--branch", "main", "--commit-dirty=true"], capture_output=True, text=True, timeout=180, env=environment)
            if process.returncode: raise ValueError("Cloudflare deployment failed: " + (process.stderr or process.stdout)[-1000:])
            # Wrangler reports a hash-prefixed deployment alias first. Cloudflare can
            # expose that alias before its TLS certificate has propagated, while the
            # canonical project hostname is stable and is updated by every deploy.
            url = f"https://{project}.pages.dev"
            publication = self.site_settings.record_publication({"dashboard_id": dashboard.get("id"), "project_name": project, "url": url, "mode": mode, "refresh_minutes": refresh, "privacy": audit})
            return JSONResponse({"data": publication}, status_code=201)
        except (FileNotFoundError, subprocess.TimeoutExpired): return _error("Cloudflare deployment requires Node.js and npx, and must finish within three minutes.", 503)
        except (json.JSONDecodeError, TypeError, ValueError) as error: return _error(str(error), 422)

    def _actor(self, request: Request, declared: str = "") -> str:
        token = request.cookies.get("phframe_session", "")
        authenticated = self.site_settings.verify_token(token)
        if authenticated:
            return authenticated
        clean = declared.strip()[:100]
        if not clean:
            raise ValueError("Your name is required for the AI audit history when the application is public.")
        return f"public:{clean}"

    async def ai_deidentify(self, request: Request) -> Response:
        dataset = self.config.datasets.get(request.path_params["dataset"])
        if not dataset:
            return _error("Dataset not found.", 404)
        try:
            payload = await request.json()
            limit = max(1, min(int(payload.get("limit", 20)), 100))
            result = deidentify_records(dataset, self.storage.list(dataset, limit=limit))
            return JSONResponse({"data": {"records": result.records, "source_rows": result.source_rows, "removed_fields": result.removed_fields, "transformed_fields": result.transformed_fields, "notice": "This technical transformation reduces exposure but is not a legal certification of de-identification."}})
        except (TypeError, ValueError) as error:
            return _error(str(error), 422)

    def _ai_evidence(self) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for item in self.config.indicators.values():
            result = self.storage.indicator(item)
            evidence.append({"kind": "indicator", **result, "endpoint": f"/api/indicators/{item.name}"})
        for item in self.config.dimensions.values():
            filters = self.config.saved_filters[item.saved_filter].values if item.saved_filter else None
            result = self.storage.dimension(item, filters)
            evidence.append({"kind": "dimension", **result, "endpoint": f"/api/dimensions/{item.name}"})
        for item in self.config.data_quality_rules.values():
            result = self.storage.data_quality(item)
            evidence.append({"kind": "quality", **result, "endpoint": f"/api/data-quality/{item.name}"})
        for item in self.config.thresholds.values():
            indicator = self.storage.indicator(self.config.indicators[item.indicator])
            actual = indicator["value"]
            comparisons = {"gt": lambda a, b: a > b, "gte": lambda a, b: a >= b, "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b, "eq": lambda a, b: a == b}
            triggered = comparisons[item.operator](actual, item.value) if actual is not None else None
            evidence.append({"kind": "threshold", "name": item.name, "label": item.label, "actual": actual, "threshold": item.value, "status": "no_data" if actual is None else ("triggered" if triggered else "normal"), "endpoint": f"/api/thresholds/{item.name}"})
        for dataset in self.config.datasets.values():
            date_fields = [name for name, field in dataset.fields.items() if field.type in {"date", "datetime"}]
            numeric_fields = [name for name, field in dataset.fields.items() if field.type in {"integer", "number"}]
            if date_fields:
                date_field = next((name for name in date_fields if name in {"report_date", "event_date", "date"}), next((name for name in date_fields if dataset.fields[name].required), date_fields[0]))
                preferred = next((name for name in numeric_fields if name in {"cases", "count", "events", "value"}), numeric_fields[0] if numeric_fields else None)
                points = self.storage.epi_curve(dataset, date_field, preferred)
                label = f"{dataset.label} over time" + (f" ({preferred.replace('_', ' ')})" if preferred else "")
                trend = enrich_trend(label, points, f"/api/epi-curve/{dataset.name}?date_field={date_field}" + (f"&value_field={preferred}" if preferred else ""))
                trend["name"] = f"{dataset.name}_{date_field}_{preferred or 'count'}_trend"; trend["dataset"] = dataset.name
                evidence.append(trend)
        return evidence

    async def ai_chat(self, request: Request) -> Response:
        session_id = request.query_params.get("session_id", "")
        if request.method == "GET":
            if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", session_id):
                return _error("A valid session_id is required.", 422)
            return JSONResponse({"data": self.storage.ai_chats(session_id)})
        try:
            payload = await request.json()
            session_id = str(payload.get("session_id", ""))
            question = str(payload.get("question", "")).strip()[:2000]
            if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", session_id):
                raise ValueError("A valid session_id is required.")
            history = self.storage.ai_chats(session_id)
            previous = [item.get("name") for item in history[-1]["evidence"]] if history else []
            answer, selected, meta = answer_question(question, self._ai_evidence(), previous)
            settings = self.site_settings.load(); provider = settings.get("ai_provider", "local")
            if provider != "local":
                answer, provider, _ = await run_in_threadpool(generate_summary, question, selected, "Answer the analyst question directly and preserve valid [E#] citations.", settings)
            privacy = {"input_scope": "selected aggregate evidence only", "protected_fields_sent": [], "row_level_records_sent": 0, "external_transfer": provider != "local"}
            chat = self.storage.record_ai_chat({"session_id": session_id, "question": question, "answer": answer, "intent": meta["intent"], "evidence_json": json.dumps(selected), "evidence_digest": evidence_digest(selected), "privacy_json": json.dumps(privacy), "actor": self._actor(request, str(payload.get("author", "")))})
            return JSONResponse({"data": chat}, status_code=201)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return _error(str(error), 422)
        except Exception as error:
            return _error(f"AI analyst request failed: {error}", 502)

    async def ai_chat_report(self, request: Request) -> Response:
        chat = self.storage.ai_chat(request.path_params["chat_id"])
        if not chat:
            return _error("AI chat answer not found.", 404)
        try:
            payload = await request.json()
            title = str(payload.get("title", f"Situation report: {chat['question']}"))[:255]
            privacy = {**chat["privacy"], "source_chat_id": chat["id"]}
            summary = self.storage.create_ai_summary({"title": title, "purpose": f"Drafted from analyst question: {chat['question']}", "content": chat["answer"], "provider": "analyst", "model": "phframe-analyst-v1", "evidence_json": json.dumps(chat["evidence"]), "evidence_digest": chat["evidence_digest"], "privacy_json": json.dumps(privacy), "created_by": self._actor(request, str(payload.get("author", "")))})
            return JSONResponse({"data": summary}, status_code=201)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return _error(str(error), 422)

    async def ai_summaries(self, request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse({"data": self.storage.ai_summaries()})
        try:
            payload = await request.json()
            title = str(payload.get("title", "Public health situation summary")).strip()[:255]
            purpose = str(payload.get("purpose", "")).strip()[:2000]
            if not title:
                raise ValueError("title is required.")
            evidence = self._ai_evidence()
            settings = self.site_settings.load()
            content, provider, model = await run_in_threadpool(generate_summary, title, evidence, purpose, settings)
            privacy = {"input_scope": "configured aggregate evidence only", "protected_fields_sent": [], "row_level_records_sent": 0, "external_transfer": provider != "local"}
            summary = self.storage.create_ai_summary({"title": title, "purpose": purpose, "content": content, "provider": provider, "model": model, "evidence_json": json.dumps(evidence), "evidence_digest": evidence_digest(evidence), "privacy_json": json.dumps(privacy), "created_by": self._actor(request, str(payload.get("author", "")))})
            return JSONResponse({"data": summary}, status_code=201)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return _error(str(error), 422)
        except Exception as error:
            return _error(f"AI provider request failed: {error}", 502)

    async def ai_summary_detail(self, request: Request) -> Response:
        summary = self.storage.ai_summary(request.path_params["summary_id"])
        return JSONResponse({"data": summary}) if summary else _error("AI summary not found.", 404)

    async def ai_summary_export(self, request: Request) -> Response:
        summary = self.storage.ai_summary(request.path_params["summary_id"])
        if not summary:
            return _error("AI summary not found.", 404)
        evidence = "\n".join(f"- {item.get('label', item.get('name'))}: {item.get('endpoint')}" for item in summary["evidence"])
        review = f"Status: {summary['status']}\nReviewed by: {summary.get('reviewed_by') or 'Not reviewed'}\nReview note: {summary.get('review_note') or 'None'}"
        warning = "> **DRAFT — NOT APPROVED FOR PUBLICATION**\n\n" if summary["status"] == "draft" else ""
        content = f"# {summary['title']}\n\n{warning}{summary['content']}\n\n---\n\n## Governance record\n\n{review}\nEvidence digest: `{summary['evidence_digest']}`\n\n## Source endpoints\n\n{evidence}\n"
        filename = re.sub(r"[^a-z0-9]+", "-", summary["title"].lower()).strip("-") or "phframe-report"
        return Response(content, media_type="text/markdown", headers={"content-disposition": f'attachment; filename="{filename}.md"'})

    async def ai_summary_review(self, request: Request) -> Response:
        try:
            payload = await request.json()
            decision = str(payload.get("decision", "")); note = str(payload.get("note", ""))[:2000]
            if not note.strip():
                raise ValueError("A review note is required for approval or rejection.")
            summary = self.storage.review_ai_summary(request.path_params["summary_id"], decision, self._actor(request, str(payload.get("reviewer", ""))), note)
            return JSONResponse({"data": summary}) if summary else _error("AI summary not found.", 404)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return _error(str(error), 422)

    async def ai_audit(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": self.storage.ai_audit()})

    async def api_index(self, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "project": self.config.name,
                "field_types": sorted(FIELD_TYPES),
                "datasets": {
                    dataset.name: {
                        "label": dataset.label,
                        "endpoint": f"/api/{dataset.name}",
                        "fields": {
                            name: {
                                "type": schema.type,
                                "required": schema.required,
                                "protected": schema.protected,
                                "label": schema.label,
                            }
                            for name, schema in dataset.fields.items()
                        },
                    }
                    for dataset in self.config.datasets.values()
                },
                "indicators": {
                    indicator.name: {
                        "label": indicator.label,
                        "dataset": indicator.dataset,
                        "operation": indicator.operation,
                        "endpoint": f"/api/indicators/{indicator.name}",
                    }
                    for indicator in self.config.indicators.values()
                },
                "data_quality": {
                    rule.name: {
                        "label": rule.label, "dataset": rule.dataset, "field": rule.field,
                        "check": rule.check, "endpoint": f"/api/data-quality/{rule.name}",
                    }
                    for rule in self.config.data_quality_rules.values()
                },
                "filters": {
                    item.name: {"label": item.label, "dataset": item.dataset, "values": item.values}
                    for item in self.config.saved_filters.values()
                },
                "dimensions": {
                    item.name: {
                        "label": item.label, "dataset": item.dataset, "field": item.field,
                        "endpoint": f"/api/dimensions/{item.name}",
                    }
                    for item in self.config.dimensions.values()
                },
                "thresholds": {
                    item.name: {
                        "label": item.label, "indicator": item.indicator, "operator": item.operator,
                        "value": item.value, "severity": item.severity,
                        "endpoint": f"/api/thresholds/{item.name}",
                    }
                    for item in self.config.thresholds.values()
                },
                "organisation_units": {
                    "count": len(self.config.organisation_units),
                    "endpoint": "/api/organisation-units",
                },
                "dashboards": {
                    item.name: {"label": item.label, "endpoint": f"/api/dashboards/{item.name}"}
                    for item in self.config.dashboards.values()
                },
                "ui": {
                    "theme": self.config.ui.theme,
                    "locale": self.config.ui.locale,
                    "translations": self.config.ui.translations,
                },
                "connectors": {
                    item.name: {
                        "type": item.type, "dataset": item.dataset,
                        "schedule_minutes": item.schedule_minutes,
                        "endpoint": f"/api/connectors/{item.name}/sync",
                    }
                    for item in self.config.connectors.values()
                },
            }
        )

    async def indicator_index(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": [
            {
                "name": item.name, "label": item.label, "dataset": item.dataset,
                "operation": item.operation, "endpoint": f"/api/indicators/{item.name}",
            }
            for item in self.config.indicators.values()
        ]})

    async def indicator_result(self, request: Request) -> Response:
        indicator = self.config.indicators.get(request.path_params["indicator"])
        if indicator is None:
            return _error("Indicator not found.", 404)
        reserved = {"start", "end", "period", "filter"}
        filters = {key: value for key, value in request.query_params.items() if key not in reserved}
        try:
            return JSONResponse({"data": self._indicator_query(indicator, request, filters)})
        except ValueError as error:
            return _error(str(error), 422)

    def _indicator_query(self, indicator: Any, request: Request, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        applied_filters = dict(filters or {})
        saved_filter_name = request.query_params.get("filter")
        if saved_filter_name:
            saved_filter = self.config.saved_filters.get(saved_filter_name)
            if saved_filter is None:
                raise ValueError(f"Saved filter '{saved_filter_name}' not found.")
            if saved_filter.dataset != indicator.dataset:
                raise ValueError(f"Saved filter '{saved_filter_name}' belongs to a different dataset.")
            applied_filters = {**saved_filter.values, **applied_filters}
        start, end = request.query_params.get("start"), request.query_params.get("end")
        period = request.query_params.get("period")
        if period:
            if start or end:
                raise ValueError("Use period or start/end, not both.")
            period_start, period_end = resolve_period(period)
            start, end = period_start.isoformat(), period_end.isoformat()
        result = self.storage.indicator(indicator, applied_filters, start, end)
        if period:
            result["period"]["name"] = period
        return result

    async def data_quality_index(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": [self.storage.data_quality(rule) for rule in self.config.data_quality_rules.values()]})

    async def data_quality_result(self, request: Request) -> Response:
        rule = self.config.data_quality_rules.get(request.path_params["rule"])
        if rule is None:
            return _error("Data-quality rule not found.", 404)
        return JSONResponse({"data": self.storage.data_quality(rule)})

    async def filter_index(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": [
            {"name": item.name, "label": item.label, "dataset": item.dataset, "values": item.values}
            for item in self.config.saved_filters.values()
        ]})

    async def dimension_index(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": [
            {"name": item.name, "label": item.label, "dataset": item.dataset, "field": item.field,
             "endpoint": f"/api/dimensions/{item.name}"}
            for item in self.config.dimensions.values()
        ]})

    async def dimension_result(self, request: Request) -> Response:
        dimension = self.config.dimensions.get(request.path_params["dimension"])
        if dimension is None:
            return _error("Dimension not found.", 404)
        saved_filter_name = request.query_params.get("filter") or dimension.saved_filter
        filters = {}
        if saved_filter_name:
            saved_filter = self.config.saved_filters.get(saved_filter_name)
            if saved_filter is None:
                return _error(f"Saved filter '{saved_filter_name}' not found.", 422)
            if saved_filter.dataset != dimension.dataset:
                return _error(f"Saved filter '{saved_filter_name}' belongs to a different dataset.", 422)
            filters.update(saved_filter.values)
        filters.update({key: value for key, value in request.query_params.items() if key != "filter"})
        try:
            return JSONResponse({"data": self.storage.dimension(dimension, filters)})
        except ValueError as error:
            return _error(str(error), 422)

    async def threshold_index(self, request: Request) -> Response:
        try:
            return JSONResponse({"data": [self._evaluate_threshold(item, request) for item in self.config.thresholds.values()]})
        except ValueError as error:
            return _error(str(error), 422)

    async def threshold_result(self, request: Request) -> Response:
        threshold = self.config.thresholds.get(request.path_params["threshold"])
        if threshold is None:
            return _error("Threshold not found.", 404)
        try:
            return JSONResponse({"data": self._evaluate_threshold(threshold, request)})
        except ValueError as error:
            return _error(str(error), 422)

    def _evaluate_threshold(self, threshold: Any, request: Request) -> dict[str, Any]:
        indicator = self.config.indicators[threshold.indicator]
        reserved = {"start", "end", "period", "filter"}
        filters = {key: value for key, value in request.query_params.items() if key not in reserved}
        result = self._indicator_query(indicator, request, filters)
        actual = result["value"]
        comparisons = {
            "gt": lambda current, target: current > target,
            "gte": lambda current, target: current >= target,
            "lt": lambda current, target: current < target,
            "lte": lambda current, target: current <= target,
            "eq": lambda current, target: current == target,
        }
        triggered = comparisons[threshold.operator](actual, threshold.value) if actual is not None else None
        return {
            "name": threshold.name, "label": threshold.label, "indicator": threshold.indicator,
            "operator": threshold.operator, "threshold": threshold.value, "actual": actual,
            "triggered": triggered, "status": "no_data" if actual is None else ("triggered" if triggered else "normal"),
            "severity": threshold.severity, "message": threshold.message,
            "filters": result["filters"], "period": result["period"],
        }

    async def organisation_unit_index(self, request: Request) -> JSONResponse:
        units = self.config.organisation_units
        return JSONResponse({
            "data": [self._organisation_unit(unit) for unit in units.values()],
            "roots": [unit.code for unit in units.values() if unit.parent is None],
            "count": len(units),
        })

    async def organisation_unit_detail(self, request: Request) -> Response:
        unit = self.config.organisation_units.get(request.path_params["code"])
        if unit is None:
            return _error("Organisation unit not found.", 404)
        result = self._organisation_unit(unit)
        ancestors = []
        parent = unit.parent
        while parent:
            ancestor = self.config.organisation_units[parent]
            ancestors.insert(0, self._organisation_unit(ancestor))
            parent = ancestor.parent
        result["ancestors"] = ancestors
        return JSONResponse({"data": result})

    def _organisation_unit(self, unit: Any) -> dict[str, Any]:
        return {
            "code": unit.code, "name": unit.name, "level": unit.level, "parent": unit.parent,
            "children": [item.code for item in self.config.organisation_units.values() if item.parent == unit.code],
            "endpoint": f"/api/organisation-units/{unit.code}",
        }

    async def dashboard(self, request: Request) -> Response:
        dashboard = self.config.dashboards.get(request.path_params["dashboard"])
        if dashboard is None:
            return _error("Dashboard not found.", 404)
        return JSONResponse({"data": {
            "name": dashboard.name, "label": dashboard.label,
            "widgets": [
                {key: value for key, value in vars(widget).items() if value is not None}
                for widget in dashboard.widgets
            ],
        }})

    async def epi_curve(self, request: Request) -> Response:
        dataset = self.config.datasets.get(request.path_params["dataset"])
        if dataset is None:
            return _error("Dataset not found.", 404)
        date_field = request.query_params.get("date_field", "")
        value_field = request.query_params.get("value_field")
        try:
            return JSONResponse({"data": self.storage.epi_curve(dataset, date_field, value_field)})
        except ValueError as error:
            return _error(str(error), 422)

    async def visualize_field(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None:
            return _error("Dataset not found.", 404)
        field = request.query_params.get("field", "")
        if field not in dataset.fields:
            return _error("Visualization field not found.", 422)
        records = self.storage.list(dataset, limit=1000)
        operation = request.query_params.get("operation")
        if operation:
            if operation not in {"sum", "average", "count"}:
                return _error("operation must be sum, average, or count.", 422)
            if operation in {"sum", "average"} and dataset.fields[field].type not in {"integer", "number", "age"}:
                return _error("sum and average require a numeric field.", 422)
            numbers = [float(record[field]) for record in records if record.get(field) is not None]
            value = len(numbers) if operation == "count" else (sum(numbers) if operation == "sum" else (sum(numbers) / len(numbers) if numbers else None))
            return JSONResponse({"data": {"label": dataset.fields[field].label or field.replace("_", " ").title(), "value": value, "operation": operation}})
        counts: dict[str, int] = {}
        for record in records:
            value = str(record.get(field) if record.get(field) not in {None, ""} else "Unknown")
            counts[value] = counts.get(value, 0) + 1
        values = [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
        return JSONResponse({"data": {"label": dataset.fields[field].label or field.replace("_", " ").title(), "values": values, "total": len(records)}})

    async def geospatial(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None: return _error("Dataset not found.", 404)
        latitude, longitude = request.query_params.get("latitude", ""), request.query_params.get("longitude", "")
        if latitude not in dataset.fields or longitude not in dataset.fields: return _error("Latitude and longitude fields were not found.", 422)
        if dataset.fields[latitude].type not in {"integer", "number"} or dataset.fields[longitude].type not in {"integer", "number"}: return _error("Coordinates must use numeric fields.", 422)
        buckets: dict[tuple[float, float], int] = {}
        for record in self.storage.list(dataset, limit=1000):
            if record.get(latitude) is None or record.get(longitude) is None: continue
            lat, lon = round(float(record[latitude]), 2), round(float(record[longitude]), 2)
            if -90 <= lat <= 90 and -180 <= lon <= 180: buckets[(lat, lon)] = buckets.get((lat, lon), 0) + 1
        points = [{"latitude": lat, "longitude": lon, "count": count} for (lat, lon), count in sorted(buckets.items())]
        return JSONResponse({"data": {"dataset": dataset.name, "latitude_field": latitude, "longitude_field": longitude, "precision": 2, "points": points, "source_rows": sum(item["count"] for item in points), "privacy": "Coordinates are aggregated into rounded 0.01-degree buckets."}})

    async def connector_index(self, request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                payload = await request.json()
                name = str(payload.pop("name", ""))
                connector = ConnectorSchema.from_dict(name, payload, self.config.datasets)
                if name in self.config.connectors:
                    raise ValueError(f"Connector already exists: {name}")
                self.config.connectors[name] = connector
                self._update_config("connectors", name, payload)
                return JSONResponse({"data": self._connector_data(connector)}, status_code=201)
            except (TypeError, ValueError) as error:
                return _error(str(error), 422)
        return JSONResponse({"data": [
            self._connector_data(item)
            for item in self.config.connectors.values()
        ]})

    def _connector_data(self, item: Any) -> dict[str, Any]:
        return {
            "name": item.name, "type": item.type, "dataset": item.dataset,
            "schedule_minutes": item.schedule_minutes, "due": connector_due(self.config, item.name),
            "sync_endpoint": f"/api/connectors/{item.name}/sync",
        }

    async def connector_delete(self, request: Request) -> Response:
        name = request.path_params["connector"]
        if name not in self.config.connectors:
            return _error("Connector not found.", 404)
        del self.config.connectors[name]
        self._update_config("connectors", name, None)
        return Response(status_code=204)

    async def connector_sync(self, request: Request) -> Response:
        name = request.path_params["connector"]
        if name not in self.config.connectors:
            return _error("Connector not found.", 404)
        dry_run = request.query_params.get("dry_run", "false").lower() == "true"
        result = await run_in_threadpool(sync_connector, self.config, name, dry_run)
        data = vars(result).copy()
        data["errors"] = list(result.errors)
        return JSONResponse({"data": data}, status_code=200 if result.status != "failed" else 502)

    async def sync_history(self, request: Request) -> Response:
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            return _error("limit must be an integer.", 400)
        return JSONResponse({"data": self.storage.sync_history(limit, request.query_params.get("connector"))})

    async def import_history(self, request: Request) -> JSONResponse:
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            return _error("limit must be an integer.", 400)
        return JSONResponse({"data": self.storage.import_history(limit)})

    async def import_errors(self, request: Request) -> Response:
        run = self.storage.import_run(request.path_params["run_id"])
        if run is None:
            return _error("Import run not found.", 404)
        return JSONResponse({"data": {
            "run_id": run["id"], "dataset": run["dataset"], "status": run["status"],
            "errors": run["errors"], "error_rows": run["error_rows"],
        }})

    async def staging_index(self, request: Request) -> Response:
        try: limit = int(request.query_params.get("limit", "50"))
        except ValueError: return _error("limit must be an integer.", 400)
        dataset = request.query_params.get("dataset")
        if dataset and dataset not in self.config.datasets: return _error("Dataset not found.", 404)
        return JSONResponse({"data": self.storage.dataset_versions(dataset, limit)})

    async def staging_detail(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if request.method == "GET":
            version = self.storage.dataset_version(version_id)
            return JSONResponse({"data": version}) if version else _error("Staged dataset version not found.", 404)
        try:
            payload = await request.json(); version = self.storage.transition_dataset_version(version_id, str(payload.get("status", "")))
            return JSONResponse({"data": version}) if version else _error("Staged dataset version not found.", 404)
        except (ValueError, json.JSONDecodeError) as error: return _error(str(error), 422)

    async def staging_rows(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if not self.storage.dataset_version(version_id): return _error("Staged dataset version not found.", 404)
        try: limit, offset = int(request.query_params.get("limit", "100")), int(request.query_params.get("offset", "0"))
        except ValueError: return _error("limit and offset must be integers.", 400)
        return JSONResponse({"data": self.storage.staged_rows(version_id, limit, offset), "limit": limit, "offset": offset})

    async def staging_quality(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        version = self.storage.dataset_version(version_id, include_rows=request.method == "POST")
        if not version: return _error("Staged dataset version not found.", 404)
        if request.method == "GET":
            report = self.storage.latest_quality_run(version_id)
            return JSONResponse({"data": report}) if report else _error("No quality review has run for this version.", 404)
        report = evaluate_quality(version["rows"], version["profile"])
        return JSONResponse({"data": self.storage.record_quality_run(version_id, report)}, status_code=201)

    async def staging_repairs(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]; version = self.storage.dataset_version(version_id, include_rows=request.method == "POST")
        if not version: return _error("Staged dataset version not found.", 404)
        quality = self.storage.latest_quality_run(version_id)
        if request.method == "GET": return JSONResponse({"data": repair_proposals(quality or {"issues": []})})
        try:
            payload = await request.json(); recipe = str(payload.get("recipe", "")); options = payload.get("options") or {}
            repaired, summary = apply_repair(version["rows"], recipe, options)
            if payload.get("preview", True):
                transformation = self.storage.record_transformation(version_id, None, recipe, "previewed", str(payload.get("actor", "user")), str(payload.get("reason", "Repair preview")), options, summary)
                return JSONResponse({"data": transformation})
            import pandas as pd
            output = stage_frame(self.config, version["dataset"], pd.DataFrame(repaired), f"repair:{version_id}:{recipe}", "transformation")
            report = evaluate_quality(repaired, output["profile"]); self.storage.record_quality_run(output["id"], report)
            transformation = self.storage.record_transformation(version_id, output["id"], recipe, "applied", str(payload.get("actor", "user")), str(payload.get("reason", "Approved repair")), options, summary)
            return JSONResponse({"data": {**transformation, "output_version": output}}, status_code=201)
        except (ValueError, json.JSONDecodeError) as error: return _error(str(error), 422)

    async def transformation_index(self, request: Request) -> Response:
        try: version_id = int(request.query_params.get("version_id", "0") or 0); limit = int(request.query_params.get("limit", "100"))
        except ValueError: return _error("version_id and limit must be integers.", 400)
        return JSONResponse({"data": self.storage.transformations(version_id or None, limit)})

    async def staging_geography(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if request.method == "GET":
            model = self.storage.geography_model(version_id)
            return JSONResponse({"data": model}) if model else _error("No geography model has run for this version.", 404)
        version = self.storage.dataset_version(version_id, include_rows=True)
        if not version: return _error("Staged dataset version not found.", 404)
        model = infer_geography(version["rows"], version["profile"])
        return JSONResponse({"data": self.storage.record_geography_model(version_id, model)}, status_code=201)

    async def staging_semantic(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if request.method == "GET":
            model = self.storage.semantic_model(version_id)
            return JSONResponse({"data": model}) if model else _error("No semantic model has been compiled for this version.", 404)
        if request.method == "PATCH":
            try: payload = await request.json(); model = self.storage.approve_semantic_model(version_id, int(payload.get("model_id", 0)))
            except (ValueError, json.JSONDecodeError): return _error("model_id must be an integer.", 422)
            return JSONResponse({"data": model}) if model else _error("Draft semantic model not found.", 404)
        version = self.storage.dataset_version(version_id)
        if not version: return _error("Staged dataset version not found.", 404)
        model = compile_semantic_model(version["profile"], self.storage.latest_quality_run(version_id), self.storage.geography_model(version_id))
        return JSONResponse({"data": self.storage.record_semantic_model(version_id, model)}, status_code=201)

    async def staging_dashboards(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if request.method == "GET": return JSONResponse({"data": self.storage.generated_dashboards(version_id)})
        semantic = self.storage.semantic_model(version_id)
        if not semantic: return _error("Compile a semantic model before generating dashboards.", 409)
        try: payload = await request.json(); variant = str(payload.get("variant", "recommended")); spec = generate_dashboard(semantic["model"], variant)
        except (ValueError, json.JSONDecodeError) as error: return _error(str(error), 422)
        if not spec["lint"]["valid"]: return _error("Generated dashboard did not pass linting.", 422)
        return JSONResponse({"data": self.storage.record_generated_dashboard(version_id, semantic["id"], variant, spec)}, status_code=201)

    async def staging_dashboard_detail(self, request: Request) -> Response:
        item = self.storage.approve_generated_dashboard(request.path_params["version_id"], request.path_params["dashboard_id"])
        return JSONResponse({"data": item}) if item else _error("Draft generated dashboard not found.", 404)

    async def intelligence_knowledge_packs(self, request: Request) -> Response:
        version_id = request.query_params.get("version_id")
        if not version_id: return JSONResponse({"data": KNOWLEDGE_PACKS})
        semantic = self.storage.semantic_model(int(version_id))
        return JSONResponse({"data": match_knowledge_packs(semantic["model"])}) if semantic else _error("Semantic model not found.", 404)

    async def staging_assistant(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]; semantic = self.storage.semantic_model(version_id)
        if not semantic: return _error("Compile a semantic model before using the dashboard assistant.", 409)
        try:
            payload = await request.json(); prompt = str(payload.get("prompt", "")); proposal = propose_change(prompt, semantic["model"])
            return JSONResponse({"data": self.storage.record_intelligence_proposal(version_id, str(payload.get("actor", "user")), prompt, proposal)}, status_code=201)
        except (ValueError, json.JSONDecodeError) as error: return _error(str(error), 422)

    async def staging_assurance(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        if request.method == "GET":
            item = self.storage.assurance_run(version_id)
            return JSONResponse({"data": item}) if item else _error("No assurance run exists for this version.", 404)
        current = self.storage.dataset_version(version_id); previous = self.storage.previous_dataset_version(version_id)
        if not current: return _error("Staged dataset version not found.", 404)
        report = assess_drift(current, previous, self.storage.latest_quality_run(version_id), self.storage.latest_quality_run(previous["id"]) if previous else None, self.storage.generated_dashboards(previous["id"]) if previous else [])
        report["evaluation"] = evaluate_assurance(report)
        return JSONResponse({"data": self.storage.record_assurance_run(version_id, previous["id"] if previous else None, report)}, status_code=201)

    async def import_mapping_index(self, request: Request) -> JSONResponse:
        return JSONResponse({"data": self.storage.mappings(request.query_params.get("dataset"))})

    async def import_mapping_save(self, request: Request) -> Response:
        name = request.path_params["name"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            return _error("Mapping name must use lowercase letters, numbers, and underscores.", 422)
        try:
            payload = await request.json()
            dataset_name = str(payload.get("dataset", ""))
            if dataset_name not in self.config.datasets:
                raise ValueError("Dataset not found.")
            mapping = payload.get("mapping")
            if not isinstance(mapping, dict) or not mapping:
                raise ValueError("mapping must be a non-empty object.")
            unknown = set(mapping.values()) - set(self.config.datasets[dataset_name].fields)
            if unknown:
                raise ValueError(f"Mapped dataset fields not found: {', '.join(sorted(unknown))}")
            clean_mapping = {str(key): str(value) for key, value in mapping.items()}
            self.storage.save_mapping(name, dataset_name, clean_mapping)
            return JSONResponse({"data": {"name": name, "dataset": dataset_name, "mapping": clean_mapping}})
        except ValueError as error:
            return _error(str(error), 422)

    async def browser_import_preview(self, request: Request) -> Response:
        try:
            frame, filename = await self._uploaded_frame(request)
            dataset = request.path_params["dataset"]
            preview = preview_frame(self.config, dataset, frame)
            version = stage_frame(self.config, dataset, frame, f"browser:{filename}")
            preview["version"] = {key: version[key] for key in ("id", "status", "content_digest", "schema_signature", "created_at")}
            report = evaluate_quality([dict(row) for row in frame.to_dict(orient="records")], preview["profile"])
            preview["quality"] = self.storage.record_quality_run(version["id"], report)
            return JSONResponse({"data": preview})
        except ValueError as error:
            return _error(str(error), 422)

    async def browser_import(self, request: Request) -> Response:
        try:
            version_id = int(request.query_params.get("version_id", "0") or 0)
            if version_id:
                version = self.storage.dataset_version(version_id, include_rows=True)
                if not version or version["dataset"] != request.path_params["dataset"]:
                    raise ValueError("Staged dataset version not found for this destination.")
                import pandas as pd
                frame, filename = pd.DataFrame(version["rows"]), Path(version["source"].removeprefix("browser:")).name
            else:
                frame, filename = await self._uploaded_frame(request)
            raw_mapping = request.query_params.get("mapping", "{}")
            mapping = json.loads(raw_mapping)
            if not isinstance(mapping, dict):
                raise ValueError("mapping must be a JSON object.")
            dry_run = request.query_params.get("dry_run", "false").lower() == "true"
            result = import_frame(
                self.config, request.path_params["dataset"], frame, f"browser:{filename}",
                {str(key): str(value) for key, value in mapping.items()}, dry_run,
            )
            if version_id and not dry_run and not result.errors:
                self.storage.approve_dataset_version(version_id)
            return JSONResponse({"data": {
                "run_id": result.run_id, "dataset": result.dataset, "status": result.status,
                "total_rows": result.total_rows, "imported_rows": result.imported_rows,
                "errors": list(result.errors), "dry_run": result.dry_run,
                "version_id": version_id or None,
            }}, status_code=200 if not result.errors else 422)
        except (json.JSONDecodeError, ValueError) as error:
            return _error(str(error), 422)

    async def _uploaded_frame(self, request: Request) -> tuple[Any, str]:
        filename = request.query_params.get("filename", "")
        if not filename:
            raise ValueError("filename is required.")
        content = await request.body()
        if not content:
            raise ValueError("The uploaded file is empty.")
        if len(content) > 25 * 1024 * 1024:
            raise ValueError("Browser imports are limited to 25 MB.")
        sheet_value = request.query_params.get("sheet", "0")
        sheet = int(sheet_value) if sheet_value.isdigit() else sheet_value
        return load_uploaded_frame(content, filename, sheet), Path(filename).name

    async def import_example(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None:
            return _error("Dataset not found.", 404)
        file_format = request.query_params.get("format", "csv").lower()
        example = {name: self._example_value(name, schema.type) for name, schema in dataset.fields.items()}
        if file_format == "json":
            content, media = json.dumps([example], indent=2), "application/json"
        elif file_format == "xml":
            fields = "".join(f"    <{name}>{escape(str(value))}</{name}>\n" for name, value in example.items())
            content, media = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<records>\n  <record>\n{fields}  </record>\n</records>\n", "application/xml"
        elif file_format == "csv":
            import csv
            from io import StringIO
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=example)
            writer.writeheader(); writer.writerow(example)
            content, media = output.getvalue(), "text/csv"
        else:
            return _error("format must be csv, json, or xml.", 422)
        return Response(content, media_type=media, headers={"content-disposition": f'attachment; filename="{dataset.name}-example.{file_format}"'})

    @staticmethod
    def _example_value(name: str, field_type: str) -> Any:
        if field_type in {"integer", "age"}: return 1
        if field_type == "number": return 1.5
        if field_type == "boolean": return True
        if field_type == "date": return "2026-08-24"
        if field_type == "datetime": return "2026-08-24T10:00:00Z"
        if field_type == "sex": return "unknown"
        if field_type == "case_classification": return "suspected"
        if field_type == "epi_week": return "2026-W35"
        if field_type == "reporting_period": return "2026-08"
        return f"example_{name}"

    async def dataset_field_create(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None:
            return _error("Dataset not found.", 404)
        try:
            payload = await request.json()
            name = str(payload.get("name", ""))
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError("Field name must use lowercase letters, numbers, and underscores.")
            if name in dataset.fields:
                raise ValueError(f"Field already exists: {name}")
            if payload.get("required"):
                raise ValueError("New browser-created fields must be optional so existing records remain valid.")
            definition = {"type": payload.get("type", "string"), "label": payload.get("label") or name.replace("_", " ").title()}
            schema = FieldSchema.from_value(definition)
            dataset.fields[name] = schema
            try:
                storage = Storage(self.config)
                storage.initialize()
            except Exception:
                del dataset.fields[name]
                raise
            self.storage = storage
            self._update_config("datasets", dataset.name, {"fields": {name: definition}}, merge=True)
            return JSONResponse({"data": {"name": name, **definition, "required": False}}, status_code=201)
        except ValueError as error:
            return _error(str(error), 422)

    def _update_config(self, section: str, name: str, value: Any, merge: bool = False) -> None:
        path = self.config.root / "phframe.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        target = raw.setdefault(section, {})
        if value is None:
            target.pop(name, None)
        elif merge and name in target:
            for key, nested in value.items():
                if isinstance(nested, dict): target[name].setdefault(key, {}).update(nested)
                else: target[name][key] = nested
        else:
            target[name] = value
        temporary = path.with_suffix(".yaml.tmp")
        temporary.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        temporary.replace(path)

    def _update_config_many(self, changes: dict[str, dict[str, Any]]) -> None:
        path = self.config.root / "phframe.yaml"; raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for section, values in changes.items(): raw.setdefault(section, {}).update(values)
        temporary = path.with_suffix(".yaml.tmp"); temporary.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"); temporary.replace(path)

    def _dataset(self, request: Request) -> DatasetSchema | None:
        return self.config.datasets.get(request.path_params["dataset"])

    async def collection(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None:
            return _error("Dataset not found.", 404)
        if request.method == "GET":
            try:
                limit = int(request.query_params.get("limit", "100"))
                offset = int(request.query_params.get("offset", "0"))
                filters = {
                    key: value for key, value in request.query_params.items()
                    if key not in {"limit", "offset", "filter"}
                }
                saved_filter_name = request.query_params.get("filter")
                if saved_filter_name:
                    saved_filter = self.config.saved_filters.get(saved_filter_name)
                    if saved_filter is None:
                        raise ValueError(f"Saved filter '{saved_filter_name}' not found.")
                    if saved_filter.dataset != dataset.name:
                        raise ValueError(f"Saved filter '{saved_filter_name}' belongs to a different dataset.")
                    filters = {**saved_filter.values, **filters}
            except ValueError:
                return _error("Invalid collection filter, limit, or offset.", 400)
            try:
                records = self.storage.list(dataset, limit, offset, filters); total = self.storage.count(dataset, filters)
            except ValueError as error:
                return _error(str(error), 422)
            return JSONResponse({"data": records, "count": len(records), "total": total, "limit": limit, "offset": offset})
        try:
            payload = await request.json()
            record = self.storage.create(dataset, payload)
            return JSONResponse({"data": record}, status_code=201)
        except ValueError as error:
            return _error(str(error), 422)

    async def detail(self, request: Request) -> Response:
        dataset = self._dataset(request)
        if dataset is None:
            return _error("Dataset not found.", 404)
        record_id = request.path_params["record_id"]
        if request.method == "GET":
            record = self.storage.get(dataset, record_id)
            return JSONResponse({"data": record}) if record else _error("Record not found.", 404)
        if request.method == "DELETE":
            return Response(status_code=204) if self.storage.delete(dataset, record_id) else _error("Record not found.", 404)
        try:
            payload = await request.json()
            record = self.storage.update(dataset, record_id, payload)
            return JSONResponse({"data": record}) if record else _error("Record not found.", 404)
        except ValueError as error:
            return _error(str(error), 422)


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "status": status}}, status_code=status)
