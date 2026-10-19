"""OpenAPI reference for the PHFrame HTTP API.

Every route in the public API contract has an operation here with its
parameters, request body, and responses. ``docs/openapi.json`` and
``docs/http-api.md`` are generated from this module, the running application
serves the same document at ``/api/openapi.json``, and the test suite checks
live responses against the documented schemas.

Regenerate both documents after an intentional change with::

    python -m public_health_framework.http_reference --write docs
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from . import __version__

OPENAPI_VERSION = "3.1.0"
JSON = "application/json"

# Paths that the application serves without a session (see PHFrame._authorized_scope).
PUBLIC_PATHS = {"/login", "/health", "/api/auth/login", "/api/auth/logout", "/api/auth/status"}

TAGS = [
    ("System", "Liveness, readiness, metadata, and the operations audit trail."),
    ("Pages", "Browser pages and static assets served by the application."),
    ("Authentication", "Session sign-in for private applications."),
    ("Settings", "Site branding, navigation, access mode, and boundary layers."),
    ("Records", "Automatically generated CRUD endpoints for each configured dataset."),
    ("Analytics", "Indicators, data-quality rules, filters, dimensions, thresholds, and visualizations."),
    ("Imports", "Browser file imports, column mappings, and import history."),
    ("Staging", "Governed staging, quality review, repair, and data-intelligence workflows."),
    ("Connectors", "Scheduled external data connectors and their sync history."),
    ("Integrations", "Cloudflare and DHIS2 account connections."),
    ("Publishing", "Privacy-reviewed dashboard publication."),
    ("AI", "Governed AI summaries, analyst chat, de-identification, and AI audit history."),
]


# ---------------------------------------------------------------- schema helpers


def ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/components/schemas/{name}"}


def string(**extra: Any) -> dict[str, Any]:
    return {"type": "string", **extra}


def integer(**extra: Any) -> dict[str, Any]:
    return {"type": "integer", **extra}


def number(**extra: Any) -> dict[str, Any]:
    return {"type": "number", **extra}


def boolean() -> dict[str, Any]:
    return {"type": "boolean"}


def array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if set(schema) == {"type"} and isinstance(schema["type"], str):
        return {"type": [schema["type"], "null"]}
    return {"anyOf": [schema, {"type": "null"}]}


def obj(properties: dict[str, Any] | None = None, optional: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    """An object whose listed properties are required unless named in ``optional``.

    Responses may gain fields in minor releases (see docs/api-stability.md), so
    additional properties are allowed unless the caller says otherwise.
    """
    properties = properties or {}
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    required = [name for name in properties if name not in optional]
    if required:
        schema["required"] = required
    schema.update(extra)
    return schema


def data(schema: dict[str, Any], **siblings: Any) -> dict[str, Any]:
    """The ``{"data": ...}`` envelope used by JSON API responses."""
    return obj({"data": schema, **siblings})


ANY_OBJECT = {"type": "object"}
STRINGS = array(string())
DATETIME = string(description="ISO 8601 timestamp.")
OPTIONAL_DATETIME = nullable(DATETIME)
SCALAR = {"type": ["string", "number", "integer", "boolean", "null"]}

COMPONENTS: dict[str, dict[str, Any]] = {
    "Error": obj({"error": obj({
        "message": string(),
        "status": integer(),
        "request_id": string(description="Present on rate-limit and body-size rejections."),
    }, optional=("status", "request_id"))}),
    "Health": obj({"status": string(enum=["ok"]), "framework": string(), "version": string(), "project": string()}),
    "Readiness": obj({
        "status": string(enum=["ready", "warning"]), "database": string(enum=["ready"]),
        "issues": array(string(description="Production configuration warning.")),
    }),
    "NotReady": obj({"status": string(enum=["not-ready"]), "error": string()}),
    "OperationsAuditEvent": obj({
        "time": DATETIME, "request_id": string(), "actor": string(), "method": string(),
        "path": string(), "status": integer(), "client": string(),
    }),
    "ApiIndex": obj({
        "project": string(), "field_types": STRINGS,
        "datasets": {"type": "object", "additionalProperties": obj({
            "label": string(), "endpoint": string(), "records": integer(description="Current row count, for an empty-project onboarding prompt."),
            "fields": {"type": "object", "additionalProperties": obj({
                "type": string(), "required": boolean(), "protected": boolean(), "label": nullable(string()),
            })},
        })},
        "indicators": ANY_OBJECT, "data_quality": ANY_OBJECT, "filters": ANY_OBJECT, "dimensions": ANY_OBJECT,
        "thresholds": ANY_OBJECT, "organisation_units": obj({"count": integer(), "endpoint": string()}),
        "dashboards": ANY_OBJECT, "ui": obj({"theme": {}, "locale": string(), "translations": ANY_OBJECT}),
        "connectors": ANY_OBJECT,
    }),
    "AuthStatus": obj({"access_mode": string(enum=["public", "private"]), "authenticated": boolean()}),
    "LoginRequest": obj({"username": string(), "password": string(format="password")}),
    "LoginResult": obj({"authenticated": boolean(), "username": string()}, optional=("username",)),
    "Settings": obj({
        "brand_name": string(), "header_title": string(), "dashboard_title": string(), "primary_color": string(),
        "default_theme": string(), "logo_url": string(), "favicon_url": string(), "access_mode": string(enum=["public", "private"]),
        "navigation": ANY_OBJECT, "has_users": boolean(),
    }),
    "SettingsUpdate": obj({
        "brand_name": string(), "header_title": string(), "dashboard_title": string(), "primary_color": string(),
        "default_theme": string(), "basemap": string(), "footer_html": string(), "show_footer": boolean(),
        "navigation": ANY_OBJECT, "pages": ANY_OBJECT, "access_mode": string(enum=["public", "private"]),
        "ai_provider": string(), "ai_model": string(), "ai_endpoint": string(), "ai_api_key_env": string(),
        "allow_external_ai": boolean(), "dashboards": array(ANY_OBJECT), "cloudflare_account_id": string(),
        "cloudflare_project_name": string(), "cloudflare_token_env": string(),
        "username": string(description="Administrator username; set together with password to create or replace the sign-in user."),
        "password": string(format="password"),
    }, optional=("brand_name", "header_title", "dashboard_title", "primary_color", "default_theme", "basemap",
                 "footer_html", "show_footer", "navigation", "pages", "access_mode", "ai_provider", "ai_model",
                 "ai_endpoint", "ai_api_key_env", "allow_external_ai", "dashboards", "cloudflare_account_id",
                 "cloudflare_project_name", "cloudflare_token_env", "username", "password")),
    "AssetUrl": obj({"url": string()}),
    "BoundaryLayer": obj({
        "id": string(), "country": nullable(string()), "iso3": nullable(string()), "level": nullable(string()),
        "year": SCALAR, "source": nullable(string()), "license": nullable(string()), "feature_count": nullable(integer()),
    }),
    "BoundaryLayerDetail": {"allOf": [ref("BoundaryLayer"), obj({"geojson": obj({"type": string(enum=["FeatureCollection"])})})]},
    "BoundaryRequest": obj({"iso3": string(pattern="^[A-Za-z]{3}$"), "level": string(pattern="^(ADM|adm)[0-5]$")}),
    "Country": obj({"name": string(), "iso3": string()}),
    "Record": obj({"id": integer(), "created_at": DATETIME, "updated_at": DATETIME},
                  description="A dataset record. Every configured dataset field is also present, typed by its field type."),
    "RecordInput": {"type": "object", "description": "Dataset field values. Unknown fields are rejected; required fields must be present on create.",
                    "additionalProperties": SCALAR},
    "RecordPage": obj({"data": array(ref("Record")), "count": integer(), "total": integer(), "limit": integer(), "offset": integer()}),
    "FieldCreate": obj({"name": string(pattern="^[a-z][a-z0-9_]*$"), "type": string(), "label": string(), "required": boolean()},
                       optional=("type", "label", "required")),
    "FieldCreated": obj({"name": string(), "type": string(), "label": string(), "required": boolean()}),
    "Period": obj({"start": nullable(string()), "end": nullable(string()), "name": string()}, optional=("name",)),
    "IndicatorSummary": obj({"name": string(), "label": string(), "dataset": string(), "operation": string(), "endpoint": string()}),
    "IndicatorResult": obj({
        "name": string(), "label": string(), "dataset": string(), "operation": string(),
        "value": nullable(number()), "multiplier": number(), "filters": ANY_OBJECT, "period": ref("Period"),
    }),
    "QualityRuleResult": obj({
        "name": string(), "label": string(), "dataset": string(), "field": string(), "check": string(),
        "total": integer(), "valid": integer(), "violations": integer(), "score": nullable(number()),
    }),
    "SavedFilter": obj({"name": string(), "label": string(), "dataset": string(), "values": ANY_OBJECT}),
    "DimensionSummary": obj({"name": string(), "label": string(), "dataset": string(), "field": string(), "endpoint": string()}),
    "DimensionResult": obj({
        "name": string(), "label": string(), "dataset": string(), "field": string(), "filters": ANY_OBJECT,
        "values": array(obj({"value": SCALAR, "count": integer()})),
    }),
    "ThresholdResult": obj({
        "name": string(), "label": string(), "indicator": string(), "operator": string(enum=["gt", "gte", "lt", "lte", "eq"]),
        "threshold": number(), "actual": nullable(number()), "triggered": nullable(boolean()),
        "status": string(enum=["normal", "triggered", "no_data"]), "severity": string(), "message": nullable(string()),
        "filters": ANY_OBJECT, "period": ref("Period"),
    }),
    "OrganisationUnit": obj({
        "code": string(), "name": string(), "level": string(), "parent": nullable(string()),
        "children": STRINGS, "endpoint": string(),
    }),
    "OrganisationUnitDetail": {"allOf": [ref("OrganisationUnit"), obj({"ancestors": array(ref("OrganisationUnit"))})]},
    "OrganisationUnitList": obj({"data": array(ref("OrganisationUnit")), "roots": STRINGS, "count": integer()}),
    "Dashboard": obj({"name": string(), "label": string(), "widgets": array(obj({"type": string()}))}),
    "EpiCurvePoint": obj({"date": string(), "value": number()}),
    "FieldDistribution": obj({"label": string(), "values": array(obj({"value": string(), "count": integer()})), "total": integer()}),
    "FieldAggregate": obj({"label": string(), "value": nullable(number()), "operation": string(enum=["sum", "average", "count"])}),
    "GeoPoints": obj({
        "dataset": string(), "latitude_field": string(), "longitude_field": string(), "precision": integer(),
        "points": array(obj({"latitude": number(), "longitude": number(), "count": integer()})),
        "source_rows": integer(), "privacy": string(),
    }),
    "ImportResult": obj({
        "run_id": nullable(integer()), "dataset": string(), "status": string(), "total_rows": integer(),
        "imported_rows": integer(), "errors": array(ANY_OBJECT), "dry_run": boolean(), "version_id": nullable(integer()),
    }),
    "ImportPreview": obj({
        "columns": STRINGS, "fields": array(obj({"name": string(), "type": string(), "required": boolean(), "label": nullable(string())})),
        "profile": ANY_OBJECT,
        "version": obj({"id": integer(), "status": string(), "content_digest": string(), "schema_signature": string(), "created_at": DATETIME}),
        "quality": ref("QualityRun"),
    }),
    "ImportRun": obj({
        "id": integer(), "dataset": string(), "source": string(), "status": string(), "total_rows": integer(),
        "imported_rows": integer(), "error_rows": integer(), "created_at": DATETIME, "errors": array(ANY_OBJECT),
    }),
    "ImportErrors": obj({"run_id": integer(), "dataset": string(), "status": string(), "errors": array(ANY_OBJECT), "error_rows": integer()}),
    "ImportMapping": obj({"name": string(), "dataset": string(), "mapping": {"type": "object", "additionalProperties": string()}}),
    "ImportMappingInput": obj({"dataset": string(), "mapping": {"type": "object", "minProperties": 1, "additionalProperties": string(),
                                                              "description": "Source column name to dataset field name."}}),
    "DatasetVersion": obj({
        "id": integer(), "dataset": string(), "source": string(), "source_kind": string(),
        "status": string(), "row_count": integer(), "column_count": integer(), "content_digest": string(),
        "schema_signature": string(), "created_at": DATETIME, "approved_at": OPTIONAL_DATETIME,
    }),
    "DatasetVersionDetail": {"allOf": [ref("DatasetVersion"), obj({"profile": obj({"row_count": integer(), "column_count": integer(), "columns": array(ANY_OBJECT)})})]},
    "StagedRow": obj({"row_number": integer(), "data": ANY_OBJECT}),
    "QualityRun": obj({
        "id": integer(), "version_id": integer(), "score": number(), "readiness": string(), "issue_count": integer(),
        "blocker_count": integer(), "created_at": DATETIME, "issues": array(ANY_OBJECT),
    }),
    "RepairProposal": obj({"recipe": string(), "safety": string(), "label": string(), "reason": string()}),
    "RepairRequest": obj({
        "recipe": string(), "options": ANY_OBJECT, "preview": {"type": "boolean", "default": True},
        "actor": string(), "reason": string(),
    }, optional=("options", "preview", "actor", "reason")),
    "Transformation": obj({
        "id": integer(), "source_version_id": integer(), "output_version_id": nullable(integer()), "recipe": string(),
        "status": string(enum=["previewed", "applied"]), "actor": string(), "reason": string(), "options": ANY_OBJECT,
        "summary": ANY_OBJECT, "created_at": DATETIME,
    }),
    "AppliedTransformation": {"allOf": [ref("Transformation"), obj({"output_version": ref("DatasetVersionDetail")})]},
    "GeographyModel": obj({"id": integer(), "version_id": integer(), "created_at": DATETIME, "model": obj({"levels": array(ANY_OBJECT), "map_ready": boolean()})}),
    "SemanticModel": obj({
        "id": integer(), "version_id": integer(), "contract_version": integer(), "status": string(enum=["draft", "approved"]),
        "created_at": DATETIME, "approved_at": OPTIONAL_DATETIME, "model": obj({"schema_signature": string(), "fields": array(ANY_OBJECT)}),
    }),
    "GeneratedDashboard": obj({
        "id": integer(), "version_id": integer(), "semantic_model_id": integer(), "variant": string(),
        "status": string(enum=["draft", "approved"]), "created_at": DATETIME, "approved_at": OPTIONAL_DATETIME,
        "spec": obj({"title": string(), "variant": string(), "widgets": array(ANY_OBJECT), "lint": ANY_OBJECT}),
    }),
    "KnowledgePack": obj({
        "id": string(), "version": string(), "name": string(), "roles": STRINGS, "views": STRINGS,
        "compatible": boolean(), "missing_roles": STRINGS, "score": integer(),
    }, optional=("compatible", "missing_roles", "score")),
    "IntelligenceProposal": obj({
        "id": integer(), "version_id": integer(), "actor": string(), "prompt": string(), "status": string(),
        "created_at": DATETIME, "reviewed_at": OPTIONAL_DATETIME,
        "proposal": obj({"action": string(), "status": string(), "requires_approval": boolean(), "change": ANY_OBJECT, "explanation": string()}),
    }),
    "AssuranceRun": obj({
        "id": integer(), "version_id": integer(), "previous_version_id": nullable(integer()), "severity": string(),
        "created_at": DATETIME,
        "report": obj({"severity": string(), "schema_changed": boolean(), "changes": array(ANY_OBJECT),
                       "affected_dashboards": array(ANY_OBJECT), "refresh_action": string(), "publish_allowed": boolean(),
                       "evaluation": obj({"passed": boolean(), "checks": ANY_OBJECT})}),
    }),
    "Connector": obj({
        "name": string(), "type": string(), "dataset": string(), "schedule_minutes": nullable(integer()),
        "due": boolean(), "sync_endpoint": string(),
    }),
    "ConnectorCreate": obj({
        "name": string(pattern="^[a-z][a-z0-9_]*$"), "type": string(enum=["api", "dhis2", "kobo", "odk"]), "dataset": string(),
        "base_url": string(format="uri"), "resource": string(),
        "mapping": {"type": "object", "minProperties": 1, "additionalProperties": string(), "description": "Source field to dataset field."},
        "records_path": string(), "parameters": ANY_OBJECT, "auth": ANY_OBJECT,
        "timeout": {"type": "integer", "minimum": 1, "maximum": 300, "default": 30}, "schedule_minutes": integer(),
    }, optional=("records_path", "parameters", "auth", "timeout", "schedule_minutes"),
        description="A connector definition with the same fields as the `connectors` section of phframe.yaml, plus its name."),
    "SyncResult": obj({
        "run_id": nullable(integer()), "connector": string(), "dataset": string(), "status": string(),
        "fetched_rows": integer(), "imported_rows": integer(), "errors": array(ANY_OBJECT), "dry_run": boolean(),
        "version_id": nullable(integer()),
    }),
    "SyncRun": obj({
        "id": integer(), "connector": string(), "dataset": string(), "status": string(), "fetched_rows": integer(),
        "imported_rows": integer(), "errors": array(ANY_OBJECT), "created_at": DATETIME,
    }),
    "CloudflareStatus": obj({
        "available": boolean(), "connected": boolean(), "account": obj({"id": string(), "name": string()}),
        "accounts": array(ANY_OBJECT), "expires_at": string(),
    }),
    "DHIS2Status": obj({
        "available": boolean(), "connected": boolean(), "method": string(), "server_url": string(),
        "user": ANY_OBJECT, "expires_at": string(),
    }),
    "DHIS2PasswordConnect": obj({"server_url": string(format="uri"), "username": string(), "password": string(format="password")}),
    "DHIS2DataSet": obj({"id": string(), "name": string()}),
    "DHIS2ImportRequest": obj({
        "data_set_id": string(), "data_set_name": string(), "local_name": string(pattern="^[a-z][a-z0-9_]*$"),
        "schedule_minutes": {"type": "integer", "default": 60},
    }, optional=("data_set_name", "schedule_minutes")),
    "DHIS2ImportResult": obj({"dataset": string(), "label": string(), "connector": ref("Connector")}),
    "PublicationRequest": obj({
        "dashboard_id": string(description="A saved dashboard id, or `configured-<name>` for a dashboard in phframe.yaml."),
        "mode": string(enum=["snapshot", "live"], default="snapshot"), "upstream_url": string(),
        "refresh_minutes": {"type": "integer", "minimum": 1, "maximum": 1440, "default": 15},
        "project_name": string(description="Cloudflare Pages project name; deploy only."),
    }, optional=("mode", "upstream_url", "refresh_minutes", "project_name")),
    "PrivacyAudit": obj({
        "approved": boolean(), "mode": string(), "dashboard_id": nullable(string()), "row_level_records": integer(),
        "protected_fields": integer(), "sources": array(ANY_OBJECT), "findings": STRINGS, "live_endpoint": string(), "notice": string(),
    }),
    "Publication": obj({
        "dashboard_id": string(), "project_name": string(), "url": string(), "mode": string(),
        "refresh_minutes": integer(), "published_at": DATETIME,
    }),
    "PublicationIndex": obj({
        "data": array(ref("Publication")),
        "cloudflare": obj({"configured": boolean(), "oauth": ref("CloudflareStatus")}),
    }),
    "PublicationSnapshot": obj({"generated_at": DATETIME, "widgets": array(obj({"type": nullable(string()), "title": string()}))}),
    "Privacy": obj({"input_scope": string(), "protected_fields_sent": array(string()), "row_level_records_sent": integer(), "external_transfer": boolean()}),
    "AISummaryRequest": obj({"title": string(), "purpose": string(), "author": string(description="Required when the application is public.")},
                            optional=("title", "purpose", "author")),
    "AISummary": obj({
        "id": integer(), "title": string(), "purpose": string(), "status": string(enum=["draft", "approved", "rejected"]),
        "content": string(format="markdown"), "provider": string(), "model": string(), "evidence": array(ANY_OBJECT),
        "evidence_digest": string(), "privacy": ANY_OBJECT, "created_by": string(), "created_at": DATETIME,
        "reviewed_by": nullable(string()), "review_note": nullable(string()), "reviewed_at": OPTIONAL_DATETIME,
    }),
    "AIReviewRequest": obj({"decision": string(enum=["approved", "rejected"]), "note": string(minLength=1), "reviewer": string()},
                           optional=("reviewer",)),
    "AIChatRequest": obj({"session_id": string(pattern="^[A-Za-z0-9_-]{8,64}$"), "question": string(maxLength=2000), "author": string()},
                         optional=("author",)),
    "AIChat": obj({
        "id": integer(), "session_id": string(), "question": string(), "answer": string(format="markdown"), "intent": string(),
        "evidence": array(ANY_OBJECT), "evidence_digest": string(), "privacy": ref("Privacy"), "actor": string(), "created_at": DATETIME,
    }),
    "AIChatReportRequest": obj({"title": string(maxLength=255), "author": string()}, optional=("title", "author")),
    "AIAuditEvent": obj({"id": integer(), "summary_id": nullable(integer()), "event": string(), "actor": string(), "created_at": DATETIME, "details": ANY_OBJECT}),
    "DeidentifyRequest": obj({"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}, optional=("limit",)),
    "DeidentifiedRecords": obj({
        "records": array(ANY_OBJECT), "source_rows": integer(), "removed_fields": STRINGS,
        "transformed_fields": STRINGS, "notice": string(),
    }),
}


# ---------------------------------------------------------------- operations


@dataclass(frozen=True)
class Response:
    description: str
    schema: dict[str, Any] | None = None
    media: str = JSON
    headers: tuple[str, ...] = ()
    also: tuple[tuple[str, dict[str, Any]], ...] = ()  # Other media types and their schemas.


@dataclass(frozen=True)
class Operation:
    method: str
    path: str  # Starlette route path, as recorded in the public API contract.
    tag: str
    summary: str
    responses: dict[int, Response]
    query: tuple[tuple[str, dict[str, Any], str], ...] = ()
    body: dict[str, Any] | None = None
    body_media: str = JSON
    body_required: bool = True
    description: str = ""


def q(name: str, schema: dict[str, Any], description: str) -> tuple[str, dict[str, Any], str]:
    return (name, schema, description)


def ok(schema: dict[str, Any], description: str = "Success.") -> Response:
    return Response(description, data(schema))


def created(schema: dict[str, Any], description: str = "Created.") -> Response:
    return Response(description, data(schema))


def error(description: str) -> Response:
    return Response(description, ref("Error"))


def html(description: str) -> Response:
    return Response(description, string(), "text/html")


def redirect(description: str) -> Response:
    return Response(description, None, "", ("location",))


NO_CONTENT = Response("Deleted.", None, "")
INVALID = error("The request body or parameters are invalid.")
BAD_QUERY = error("A query parameter is not a valid integer.")
NOT_FOUND = error("Not found.")
UPSTREAM = error("The external service could not be reached or rejected the request.")
LIMIT = q("limit", integer(), "Maximum number of items to return.")

OPERATIONS: list[Operation] = [
    # System
    Operation("GET", "/health", "System", "Liveness check", {200: Response("The application is running.", ref("Health"))}),
    Operation("GET", "/ready", "System", "Readiness check", {
        200: Response("The database is reachable. `warning` lists production configuration issues.", ref("Readiness")),
        503: Response("The database or configuration is not ready.", ref("NotReady")),
    }),
    Operation("GET", "/api", "System", "Project metadata", {200: Response("Datasets, analytics definitions, dashboards, UI, and connectors configured for the project.", ref("ApiIndex"))}),
    Operation("GET", "/api/openapi.json", "System", "OpenAPI document", {200: Response("This reference as an OpenAPI 3.1 document.", ANY_OBJECT)}),
    Operation("GET", "/api/operations/audit", "System", "Operations audit trail", {200: ok(array(ref("OperationsAuditEvent")))},
              query=(q("limit", integer(default=100, maximum=1000), "Most recent events to return."),),
              description="Every write request (any method other than GET, HEAD, or OPTIONS), newest first."),
    # Pages and assets
    Operation("GET", "/", "Pages", "Project home page", {200: html("A page linking to the datasets, application, and API metadata.")}),
    Operation("GET", "/app", "Pages", "Application shell", {200: html("The single-page application shell.")}),
    Operation("GET", "/login", "Pages", "Sign-in page", {200: html("The branded sign-in form.")}),
    Operation("GET", "/assets/phframe.css", "Pages", "Application stylesheet", {200: Response("Stylesheet.", string(), "text/css")}),
    Operation("GET", "/assets/phframe.js", "Pages", "Application script", {200: Response("JavaScript module.", string(), "text/javascript")}),
    Operation("GET", "/assets/leaflet.css", "Pages", "Pinned Leaflet stylesheet", {200: Response("Leaflet 1.9.4 stylesheet, served locally so the content security policy can stay self-only.", string(), "text/css")}),
    Operation("GET", "/assets/leaflet.js", "Pages", "Pinned Leaflet script", {200: Response("Leaflet 1.9.4 script.", string(), "text/javascript")}),
    Operation("GET", "/assets/gridstack.css", "Pages", "Pinned GridStack stylesheet", {200: Response("GridStack 14.0.0 stylesheet, served locally so the content security policy can stay self-only.", string(), "text/css")}),
    Operation("GET", "/assets/gridstack.js", "Pages", "Pinned GridStack script", {200: Response("GridStack 14.0.0 script, powering free drag-and-drop dashboard layout.", string(), "text/javascript")}),
    Operation("GET", "/assets/chart.js", "Pages", "Pinned Chart.js script", {200: Response("Chart.js 4.5.1 script, served locally so the content security policy can stay self-only.", string(), "text/javascript")}),
    Operation("GET", "/assets/phframe-logo.png", "Pages", "PHFrame logo", {200: Response("PNG image.", string(format="binary"), "image/png")}),
    Operation("GET", "/assets/project/{kind}", "Pages", "Project brand asset", {
        200: Response("The uploaded logo or favicon.", string(format="binary"), "image/*"),
        404: NOT_FOUND,
    }),
    # Authentication
    Operation("GET", "/api/auth/status", "Authentication", "Session status", {200: ok(ref("AuthStatus"))}),
    Operation("POST", "/api/auth/login", "Authentication", "Sign in", {
        200: Response("Signed in; sets the `phframe_session` cookie for 24 hours.", data(ref("LoginResult")), headers=("set-cookie",)),
        400: error("The body is not a JSON object."),
        401: error("Invalid username or password."),
    }, body=ref("LoginRequest"), description="Limited to 10 attempts per client per minute."),
    Operation("POST", "/api/auth/logout", "Authentication", "Sign out", {200: Response("Signed out; clears the session cookie.", data(ref("LoginResult")), headers=("set-cookie",))},
              body_required=False),
    # Settings
    Operation("GET", "/api/settings", "Settings", "Read site settings", {200: ok(ref("Settings"))}),
    Operation("PUT", "/api/settings", "Settings", "Update site settings", {200: ok(ref("Settings")), 422: INVALID}, body=ref("SettingsUpdate"),
              description="Unknown keys are ignored. Returns the public settings after the update; user credentials are never returned."),
    Operation("POST", "/api/settings/assets/{kind}", "Settings", "Upload a brand asset", {200: ok(ref("AssetUrl")), 422: INVALID},
              query=(q("filename", string(), "Original file name; its extension selects the image type."),),
              body=string(format="binary"), body_media="application/octet-stream", description="`kind` is `logo` or `favicon`."),
    Operation("GET", "/api/boundaries", "Settings", "List boundary layers", {200: ok(array(ref("BoundaryLayer")))}),
    Operation("POST", "/api/boundaries", "Settings", "Download a boundary layer", {201: created(ref("BoundaryLayer")), 422: INVALID},
              body=ref("BoundaryRequest"), description="Downloads an openly licensed geoBoundaries layer and stores it in the project."),
    Operation("GET", "/api/boundaries/countries", "Settings", "List boundary countries", {200: ok(array(ref("Country"))), 502: UPSTREAM}),
    Operation("GET", "/api/boundaries/{boundary_id}", "Settings", "Read a boundary layer", {200: ok(ref("BoundaryLayerDetail")), 404: NOT_FOUND}),
    # Records
    Operation("GET", "/api/{dataset}", "Records", "List records", {
        200: Response("A page of records.", ref("RecordPage")),
        400: error("limit or offset is not an integer, or the saved filter is unknown or belongs to another dataset."),
        404: NOT_FOUND, 422: error("A filter names an unknown field or has an invalid value."),
    }, query=(
        q("limit", integer(default=100), "Page size."), q("offset", integer(default=0), "Records to skip."),
        q("filter", string(), "Name of a saved filter for this dataset."),
        q("{field}", string(), "Any other parameter filters on the dataset field of that name (equality)."),
    )),
    Operation("POST", "/api/{dataset}", "Records", "Create a record", {201: created(ref("Record")), 404: NOT_FOUND, 422: INVALID}, body=ref("RecordInput")),
    Operation("GET", "/api/{dataset}/{record_id:int}", "Records", "Read a record", {200: ok(ref("Record")), 404: NOT_FOUND}),
    Operation("PUT", "/api/{dataset}/{record_id:int}", "Records", "Replace a record", {200: ok(ref("Record")), 404: NOT_FOUND, 422: INVALID}, body=ref("RecordInput")),
    Operation("PATCH", "/api/{dataset}/{record_id:int}", "Records", "Update record fields", {200: ok(ref("Record")), 404: NOT_FOUND, 422: INVALID}, body=ref("RecordInput")),
    Operation("DELETE", "/api/{dataset}/{record_id:int}", "Records", "Delete a record", {204: NO_CONTENT, 404: NOT_FOUND}),
    Operation("POST", "/api/project/datasets/{dataset}/fields", "Records", "Add an optional field to a dataset", {201: created(ref("FieldCreated")), 404: NOT_FOUND, 422: INVALID},
              body=ref("FieldCreate"), description="Adds the column to the database and to phframe.yaml. New fields must be optional."),
    # Analytics
    Operation("GET", "/api/indicators", "Analytics", "List indicators", {200: ok(array(ref("IndicatorSummary")))}),
    Operation("GET", "/api/indicators/{indicator}", "Analytics", "Calculate an indicator", {200: ok(ref("IndicatorResult")), 404: NOT_FOUND, 422: INVALID}, query=(
        q("start", string(format="date"), "Earliest date to include."), q("end", string(format="date"), "Latest date to include."),
        q("period", string(), "A named relative period such as `last_7_days`; not combined with start/end."),
        q("filter", string(), "Name of a saved filter."), q("{field}", string(), "Any other parameter filters on that dataset field."),
    )),
    Operation("GET", "/api/data-quality", "Analytics", "Evaluate all data-quality rules", {200: ok(array(ref("QualityRuleResult")))}),
    Operation("GET", "/api/data-quality/{rule}", "Analytics", "Evaluate a data-quality rule", {200: ok(ref("QualityRuleResult")), 404: NOT_FOUND}),
    Operation("GET", "/api/filters", "Analytics", "List saved filters", {200: ok(array(ref("SavedFilter")))}),
    Operation("GET", "/api/dimensions", "Analytics", "List dimensions", {200: ok(array(ref("DimensionSummary")))}),
    Operation("GET", "/api/dimensions/{dimension}", "Analytics", "Break down a dimension", {200: ok(ref("DimensionResult")), 404: NOT_FOUND, 422: INVALID},
              query=(q("filter", string(), "Name of a saved filter."), q("{field}", string(), "Any other parameter filters on that dataset field."))),
    Operation("GET", "/api/thresholds", "Analytics", "Evaluate all thresholds", {200: ok(array(ref("ThresholdResult"))), 422: INVALID},
              query=(q("start", string(format="date"), "Earliest date."), q("end", string(format="date"), "Latest date."), q("period", string(), "Named relative period."))),
    Operation("GET", "/api/thresholds/{threshold}", "Analytics", "Evaluate a threshold", {200: ok(ref("ThresholdResult")), 404: NOT_FOUND, 422: INVALID},
              query=(q("start", string(format="date"), "Earliest date."), q("end", string(format="date"), "Latest date."), q("period", string(), "Named relative period."))),
    Operation("GET", "/api/organisation-units", "Analytics", "List organisation units", {200: Response("The organisation unit hierarchy.", ref("OrganisationUnitList"))}),
    Operation("GET", "/api/organisation-units/{code}", "Analytics", "Read an organisation unit", {200: ok(ref("OrganisationUnitDetail")), 404: NOT_FOUND}),
    Operation("GET", "/api/dashboards/{dashboard}", "Analytics", "Read a configured dashboard", {200: ok(ref("Dashboard")), 404: NOT_FOUND}),
    Operation("GET", "/api/epi-curve/{dataset}", "Analytics", "Epidemic curve", {200: ok(array(ref("EpiCurvePoint"))), 404: NOT_FOUND, 422: INVALID},
              query=(q("date_field", string(), "Date field to group by."), q("value_field", string(), "Numeric field to sum; counts records when omitted."))),
    Operation("GET", "/api/visualize/{dataset}", "Analytics", "Visualize one field", {
        200: Response("A value distribution, or an aggregate when `operation` is given.", data({"oneOf": [ref("FieldDistribution"), ref("FieldAggregate")]})),
        404: NOT_FOUND, 422: INVALID,
    }, query=(q("field", string(), "Dataset field to visualize."), q("operation", string(enum=["sum", "average", "count"]), "Aggregate instead of a distribution.")),
        description="Reads at most the first 1,000 records."),
    Operation("GET", "/api/geospatial/{dataset}", "Analytics", "Aggregated coordinates", {200: ok(ref("GeoPoints")), 404: NOT_FOUND, 422: INVALID},
              query=(q("latitude", string(), "Numeric latitude field."), q("longitude", string(), "Numeric longitude field.")),
              description="Coordinates are rounded to 0.01-degree buckets so individual locations are not exposed."),
    # Imports
    Operation("POST", "/api/browser-import/{dataset}/preview", "Imports", "Preview and stage an uploaded file", {200: ok(ref("ImportPreview")), 422: INVALID},
              query=(q("filename", string(), "File name; its extension selects CSV, Excel, JSON, or XML parsing."), q("sheet", string(default="0"), "Excel sheet index or name.")),
              body=string(format="binary"), body_media="application/octet-stream",
              description="Stages the upload as an immutable dataset version and runs a quality review. Uploads are limited to 25 MB."),
    Operation("POST", "/api/browser-import/{dataset}", "Imports", "Import an uploaded file or staged version", {
        200: ok(ref("ImportResult")), 422: Response("The import had row errors, or the request is invalid.", {"oneOf": [data(ref("ImportResult")), ref("Error")]}),
    }, query=(
        q("filename", string(), "File name, when uploading a file."), q("sheet", string(default="0"), "Excel sheet index or name."),
        q("version_id", integer(), "Import a staged version instead of an upload; approves it on success."),
        q("mapping", string(description="JSON object."), "Source column to dataset field mapping, as JSON."),
        q("dry_run", boolean(), "Validate without writing records."),
    ), body=string(format="binary"), body_media="application/octet-stream", body_required=False),
    Operation("GET", "/api/import-example/{dataset}", "Imports", "Download an example import file", {
        200: Response("A one-row example in the requested format.", string(), "text/csv", ("content-disposition",),
                      (("application/json", array(ANY_OBJECT)), ("application/xml", string()))),
        404: NOT_FOUND, 422: INVALID,
    }, query=(q("format", string(enum=["csv", "json", "xml"], default="csv"), "File format."),)),
    Operation("GET", "/api/import-mappings", "Imports", "List saved column mappings", {200: ok(array(ref("ImportMapping")))},
              query=(q("dataset", string(), "Only mappings for this dataset."),)),
    Operation("PUT", "/api/import-mappings/{name}", "Imports", "Save a column mapping", {200: ok(ref("ImportMapping")), 422: INVALID}, body=ref("ImportMappingInput")),
    Operation("GET", "/api/imports", "Imports", "Import history", {200: ok(array(ref("ImportRun"))), 400: BAD_QUERY}, query=(q("limit", integer(default=20, maximum=200), "Most recent runs to return."),)),
    Operation("GET", "/api/imports/{run_id:int}/errors", "Imports", "Import run errors", {200: ok(ref("ImportErrors")), 404: NOT_FOUND}),
    # Staging and data intelligence
    Operation("GET", "/api/staging", "Staging", "List staged dataset versions", {200: ok(array(ref("DatasetVersion"))), 400: BAD_QUERY, 404: NOT_FOUND},
              query=(q("limit", integer(default=50, maximum=200), "Most recent versions to return."), q("dataset", string(), "Only versions of this dataset."))),
    Operation("GET", "/api/staging/{version_id:int}", "Staging", "Read a staged version", {200: ok(ref("DatasetVersionDetail")), 404: NOT_FOUND}),
    Operation("PATCH", "/api/staging/{version_id:int}", "Staging", "Change a staged version's status", {200: ok(ref("DatasetVersionDetail")), 404: NOT_FOUND, 422: INVALID},
              body=obj({"status": string()})),
    Operation("GET", "/api/staging/{version_id:int}/rows", "Staging", "Read staged rows", {
        200: Response("A page of staged source rows.", obj({"data": array(ref("StagedRow")), "limit": integer(), "offset": integer()})),
        400: BAD_QUERY, 404: NOT_FOUND,
    }, query=(q("limit", integer(default=100), "Page size."), q("offset", integer(default=0), "Rows to skip."))),
    Operation("GET", "/api/staging/{version_id:int}/quality", "Staging", "Latest quality review", {200: ok(ref("QualityRun")), 404: NOT_FOUND}),
    Operation("POST", "/api/staging/{version_id:int}/quality", "Staging", "Run a quality review", {201: created(ref("QualityRun")), 404: NOT_FOUND}, body_required=False),
    Operation("GET", "/api/staging/{version_id:int}/repairs", "Staging", "Proposed repairs", {200: ok(array(ref("RepairProposal"))), 404: NOT_FOUND}),
    Operation("POST", "/api/staging/{version_id:int}/repairs", "Staging", "Preview or apply a repair", {
        200: ok(ref("Transformation"), "Preview recorded (`preview` true)."),
        201: created(ref("AppliedTransformation"), "Repair applied as a new staged version."),
        404: NOT_FOUND, 422: INVALID,
    }, body=ref("RepairRequest")),
    Operation("GET", "/api/transformations", "Staging", "Transformation history", {200: ok(array(ref("Transformation"))), 400: BAD_QUERY},
              query=(q("version_id", integer(), "Only transformations that read or wrote this version."), q("limit", integer(default=100, maximum=500), "Most recent to return."))),
    Operation("GET", "/api/staging/{version_id:int}/geography", "Staging", "Latest geography model", {200: ok(ref("GeographyModel")), 404: NOT_FOUND}),
    Operation("POST", "/api/staging/{version_id:int}/geography", "Staging", "Infer a geography model", {201: created(ref("GeographyModel")), 404: NOT_FOUND}, body_required=False),
    Operation("GET", "/api/staging/{version_id:int}/semantic", "Staging", "Latest semantic model", {200: ok(ref("SemanticModel")), 404: NOT_FOUND}),
    Operation("POST", "/api/staging/{version_id:int}/semantic", "Staging", "Compile a draft semantic model", {201: created(ref("SemanticModel")), 404: NOT_FOUND}, body_required=False),
    Operation("PATCH", "/api/staging/{version_id:int}/semantic", "Staging", "Approve a semantic model", {200: ok(ref("SemanticModel")), 404: NOT_FOUND, 422: INVALID},
              body=obj({"model_id": integer()})),
    Operation("GET", "/api/staging/{version_id:int}/dashboards", "Staging", "Generated dashboards", {200: ok(array(ref("GeneratedDashboard")))}),
    Operation("POST", "/api/staging/{version_id:int}/dashboards", "Staging", "Generate a dashboard", {
        201: created(ref("GeneratedDashboard")), 409: error("No semantic model has been compiled for this version."), 422: INVALID,
    }, body=obj({"variant": string(default="recommended")}, optional=("variant",)), body_required=False),
    Operation("PATCH", "/api/staging/{version_id:int}/dashboards/{dashboard_id:int}", "Staging", "Approve a generated dashboard", {200: ok(ref("GeneratedDashboard")), 404: NOT_FOUND},
              body_required=False),
    Operation("GET", "/api/intelligence/knowledge-packs", "Staging", "Public-health knowledge packs", {200: ok(array(ref("KnowledgePack"))), 404: NOT_FOUND},
              query=(q("version_id", integer(), "Score each pack against this version's semantic model."),)),
    Operation("POST", "/api/staging/{version_id:int}/assistant", "Staging", "Propose a dashboard change", {
        201: created(ref("IntelligenceProposal")), 409: error("No semantic model has been compiled for this version."), 422: INVALID,
    }, body=obj({"prompt": string(), "actor": string()}, optional=("actor",)),
        description="Records a proposal constrained to the semantic contract. Nothing changes until a person approves it."),
    Operation("GET", "/api/staging/{version_id:int}/assurance", "Staging", "Latest assurance run", {200: ok(ref("AssuranceRun")), 404: NOT_FOUND}),
    Operation("POST", "/api/staging/{version_id:int}/assurance", "Staging", "Check drift against the previous version", {201: created(ref("AssuranceRun")), 404: NOT_FOUND}, body_required=False),
    # Connectors
    Operation("GET", "/api/connectors", "Connectors", "List connectors", {200: ok(array(ref("Connector")))}),
    Operation("POST", "/api/connectors", "Connectors", "Create a connector", {201: created(ref("Connector")), 422: INVALID}, body=ref("ConnectorCreate"),
              description="Validates the definition and saves it to phframe.yaml."),
    Operation("DELETE", "/api/connectors/{connector}", "Connectors", "Delete a connector", {204: NO_CONTENT, 404: NOT_FOUND}),
    Operation("POST", "/api/connectors/{connector}/sync", "Connectors", "Run a connector sync", {
        200: ok(ref("SyncResult")), 404: NOT_FOUND, 502: Response("The sync failed.", data(ref("SyncResult"))),
    }, query=(q("dry_run", boolean(), "Fetch and validate without importing."),), body_required=False),
    Operation("GET", "/api/syncs", "Connectors", "Sync history", {200: ok(array(ref("SyncRun"))), 400: BAD_QUERY},
              query=(q("limit", integer(default=20, maximum=200), "Most recent runs to return."), q("connector", string(), "Only runs of this connector."))),
    # Integrations
    Operation("GET", "/api/integrations/cloudflare/status", "Integrations", "Cloudflare connection status", {200: ok(ref("CloudflareStatus"))}),
    Operation("GET", "/api/integrations/cloudflare/connect", "Integrations", "Start Cloudflare authorization", {
        303: redirect("Redirects to Cloudflare, or to the PHFrame authorization broker when no client secret is configured."),
        503: error("Cloudflare authorization is not configured."),
    }),
    Operation("GET", "/api/integrations/cloudflare/callback", "Integrations", "Cloudflare OAuth callback", {303: redirect("Redirects to the settings page with the outcome.")},
              query=(q("code", string(), "Authorization code."), q("state", string(), "State issued by connect."), q("error", string(), "Set when authorization was denied."))),
    Operation("GET", "/api/integrations/cloudflare/broker/callback", "Integrations", "Authorization broker callback", {303: redirect("Redirects to the settings page with the outcome.")},
              query=(q("broker_code", string(), "Single-use broker grant."), q("state", string(), "State issued by connect."))),
    Operation("PUT", "/api/integrations/cloudflare/account", "Integrations", "Select a Cloudflare account", {200: ok(ref("CloudflareStatus")), 422: INVALID},
              body=obj({"account_id": string()})),
    Operation("POST", "/api/integrations/cloudflare/disconnect", "Integrations", "Disconnect Cloudflare", {200: ok(ref("CloudflareStatus"))}, body_required=False),
    Operation("GET", "/api/integrations/dhis2/status", "Integrations", "DHIS2 connection status", {200: ok(ref("DHIS2Status"))}),
    Operation("GET", "/api/integrations/dhis2/connect", "Integrations", "Start DHIS2 authorization", {
        303: redirect("Redirects to the DHIS2 server's authorization page."), 503: error("DHIS2 OAuth is not configured or the server URL is invalid."),
    }, query=(q("server_url", string(format="uri"), "DHIS2 server base URL."),)),
    Operation("POST", "/api/integrations/dhis2/password-connect", "Integrations", "Connect DHIS2 with a username and password", {200: ok(ref("DHIS2Status")), 422: INVALID},
              body=ref("DHIS2PasswordConnect")),
    Operation("GET", "/api/integrations/dhis2/callback", "Integrations", "DHIS2 OAuth callback", {303: redirect("Redirects to the connectors page with the outcome.")},
              query=(q("code", string(), "Authorization code."), q("state", string(), "State issued by connect."), q("error", string(), "Set when authorization was denied."))),
    Operation("GET", "/api/integrations/dhis2/data-sets", "Integrations", "List DHIS2 data sets", {200: ok(array(ref("DHIS2DataSet"))), 502: UPSTREAM}),
    Operation("POST", "/api/integrations/dhis2/import-data-set", "Integrations", "Create a dataset and connector from a DHIS2 data set", {201: created(ref("DHIS2ImportResult")), 422: INVALID},
              body=ref("DHIS2ImportRequest")),
    Operation("POST", "/api/integrations/dhis2/disconnect", "Integrations", "Disconnect DHIS2", {200: ok(ref("DHIS2Status"))}, body_required=False),
    # Publishing
    Operation("GET", "/api/publications", "Publishing", "List publications", {200: Response("Published dashboards and Cloudflare readiness.", ref("PublicationIndex"))}),
    Operation("GET", "/api/publications/feed/{dashboard_id}", "Publishing", "Aggregate dashboard feed", {
        200: Response("Aggregate widget data for a live published dashboard; cacheable for 60 seconds.", ref("PublicationSnapshot")),
        422: error("The dashboard was not found or failed the privacy review."),
    }),
    Operation("POST", "/api/publications/preview", "Publishing", "Run the publication privacy review", {200: ok(ref("PrivacyAudit")), 422: INVALID}, body=ref("PublicationRequest")),
    Operation("POST", "/api/publications/bundle", "Publishing", "Download a Cloudflare Pages bundle", {
        200: Response("A zip archive ready for Cloudflare Pages.", string(format="binary"), "application/zip", ("content-disposition",)), 422: INVALID,
    }, body=ref("PublicationRequest")),
    Operation("POST", "/api/publications/deploy", "Publishing", "Deploy to Cloudflare Pages", {
        201: created(ref("Publication")), 422: INVALID, 503: error("Node.js and npx are unavailable, or the deployment timed out."),
    }, body=ref("PublicationRequest")),
    # AI
    Operation("POST", "/api/ai/deidentify/{dataset}", "AI", "De-identify a sample of records", {200: ok(ref("DeidentifiedRecords")), 404: NOT_FOUND, 422: INVALID},
              body=ref("DeidentifyRequest")),
    Operation("GET", "/api/ai/chat", "AI", "Analyst chat history", {200: ok(array(ref("AIChat"))), 422: INVALID},
              query=(q("session_id", string(pattern="^[A-Za-z0-9_-]{8,64}$"), "Chat session identifier."),)),
    Operation("POST", "/api/ai/chat", "AI", "Ask the analyst", {201: created(ref("AIChat")), 422: INVALID, 502: UPSTREAM}, body=ref("AIChatRequest"),
              description="Answers from aggregate project evidence with citations. Row-level records are never sent to a provider."),
    Operation("POST", "/api/ai/chat/{chat_id:int}/report", "AI", "Draft a report from a chat answer", {201: created(ref("AISummary")), 404: NOT_FOUND, 422: INVALID},
              body=ref("AIChatReportRequest")),
    Operation("GET", "/api/ai/summaries", "AI", "List AI summaries", {200: ok(array(ref("AISummary")))}),
    Operation("POST", "/api/ai/summaries", "AI", "Generate an AI summary draft", {201: created(ref("AISummary")), 422: INVALID, 502: UPSTREAM}, body=ref("AISummaryRequest")),
    Operation("GET", "/api/ai/summaries/{summary_id:int}", "AI", "Read an AI summary", {200: ok(ref("AISummary")), 404: NOT_FOUND}),
    Operation("GET", "/api/ai/summaries/{summary_id:int}/export", "AI", "Export an AI summary as Markdown", {
        200: Response("Markdown report with its governance record.", string(), "text/markdown", ("content-disposition",)), 404: NOT_FOUND,
    }),
    Operation("POST", "/api/ai/summaries/{summary_id:int}/review", "AI", "Approve or reject an AI summary", {200: ok(ref("AISummary")), 404: NOT_FOUND, 422: INVALID},
              body=ref("AIReviewRequest")),
    Operation("GET", "/api/ai/audit", "AI", "AI audit history", {200: ok(array(ref("AIAuditEvent")))}),
]


# ---------------------------------------------------------------- OpenAPI document

_PARAMETER = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?}")


def openapi_path(path: str) -> str:
    """Strip Starlette converters: ``/api/{id:int}`` becomes ``/api/{id}``."""
    return _PARAMETER.sub(lambda match: "{" + match.group(1) + "}", path)


def _path_parameters(path: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "in": "path", "required": True, "schema": integer() if converter == "int" else string()}
        for name, converter in _PARAMETER.findall(path)
    ]


def _response(item: Response) -> dict[str, Any]:
    result: dict[str, Any] = {"description": item.description}
    if item.media:
        result["content"] = {media: {"schema": schema} for media, schema in ((item.media, item.schema or {}), *item.also)}
    if item.headers:
        result["headers"] = {name: {"schema": string()} for name in item.headers}
    return result


# Responses added to every operation that can produce them.
_AUTH_REQUIRED = "Authentication required (private applications only)."
_LOGIN_REDIRECT = "Redirects to /login when the application is private and there is no session."
_RATE_LIMITED = "Rate limit exceeded; retry after the `retry-after` header."


def _requires_session(path: str) -> bool:
    return path not in PUBLIC_PATHS and not path.startswith("/assets/")


def _operation(item: Operation) -> dict[str, Any]:
    responses = dict(item.responses)
    if _requires_session(item.path) and item.path.startswith("/api"):
        responses.setdefault(401, error(_AUTH_REQUIRED))
    elif _requires_session(item.path):
        responses.setdefault(303, redirect(_LOGIN_REDIRECT))
    responses.setdefault(429, error(_RATE_LIMITED))
    operation: dict[str, Any] = {
        "operationId": _operation_id(item),
        "tags": [item.tag],
        "summary": item.summary,
    }
    if item.description:
        operation["description"] = item.description
    parameters = _path_parameters(item.path) + [
        {"name": name, "in": "query", "required": False, "description": description, "schema": schema}
        for name, schema, description in item.query
    ]
    if parameters:
        operation["parameters"] = parameters
    if item.body is not None:
        operation["requestBody"] = {"required": item.body_required, "content": {item.body_media: {"schema": item.body}}}
    operation["responses"] = {str(status): _response(responses[status]) for status in sorted(responses)}
    if not _requires_session(item.path):
        operation["security"] = []
    return operation


def _operation_id(item: Operation) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", item.summary.lower()).split()
    return words[0] + "".join(word.title() for word in words[1:])


def build_openapi() -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {}
    for item in OPERATIONS:
        paths.setdefault(openapi_path(item.path), {})[item.method.lower()] = _operation(item)
    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "PHFrame HTTP API",
            "version": __version__,
            "summary": "Generated dataset, analytics, data-intelligence, publishing, and governed AI APIs.",
            "description": (
                "Routes and methods are covered by the PHFrame stability policy (docs/api-stability.md). "
                "Record endpoints are generated for every dataset in phframe.yaml, so `{dataset}` is a configured dataset name "
                "and record fields follow that dataset's schema. JSON responses wrap results in `data`; errors use the `Error` schema. "
                "When `access_mode` is `private`, requests need a `phframe_session` cookie from `/api/auth/login`; "
                "write requests may instead send `Authorization: Bearer $PHFRAME_API_TOKEN`."
            ),
            "license": {"name": "MIT", "identifier": "MIT"},
        },
        "tags": [{"name": name, "description": description} for name, description in TAGS],
        "paths": dict(sorted(paths.items())),
        "components": {
            "schemas": COMPONENTS,
            "securitySchemes": {
                "session": {"type": "apiKey", "in": "cookie", "name": "phframe_session"},
                "apiToken": {"type": "http", "scheme": "bearer", "description": "PHFRAME_API_TOKEN; accepted for write requests only."},
            },
        },
        "security": [{"session": []}, {"apiToken": []}],
    }


def operation_keys() -> set[str]:
    return {f"{item.method} {item.path}" for item in OPERATIONS}


# ---------------------------------------------------------------- Markdown reference


def _type(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "—"
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return f"[`{name}`](#{name.lower()})"
    if "anyOf" in schema:
        options = [option for option in schema["anyOf"] if option != {"type": "null"}]
        return " \\| ".join(_type(option) for option in options) + (" or null" if len(options) < len(schema["anyOf"]) else "")
    if "oneOf" in schema:
        return " or ".join(_type(option) for option in schema["oneOf"])
    if "allOf" in schema:
        return " + ".join(_type(option) for option in schema["allOf"])
    kind = schema.get("type", "any")
    if isinstance(kind, list):
        return " or ".join(kind)
    if kind == "array":
        return f"array of {_type(schema.get('items'))}"
    if kind == "object" and set(schema.get("properties", {})) == {"data"}:
        return "`data`: " + _type(schema["properties"]["data"])
    if kind == "object" and schema.get("properties"):
        return "object (" + ", ".join(f"`{name}`" for name in schema["properties"]) + ")"
    detail = schema.get("format") or (", ".join(schema["enum"]) if "enum" in schema else "")
    return f"{kind} ({detail})" if detail else kind


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _fields(schema: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    parts = schema.get("allOf", [schema])
    for part in parts:
        if "$ref" in part:
            lines.append(f"Includes every field of {_type(part)}.")
            lines.append("")
            continue
        if schema.get("description") and part is schema:
            lines += [schema["description"], ""]
        properties = part.get("properties", {})
        if properties:
            required = set(part.get("required", []))
            lines += ["| Field | Type | Required | Notes |", "|---|---|---|---|"]
            for name, value in properties.items():
                lines.append(f"| `{name}` | {_cell(_type(value))} | {'yes' if name in required else 'no'} | {_cell(value.get('description', ''))} |")
            lines.append("")
        elif part.get("additionalProperties"):
            lines += [f"A map of names to {_type(part['additionalProperties'])}.", ""]
    return lines


_COMMON = {_AUTH_REQUIRED, _LOGIN_REDIRECT, _RATE_LIMITED}  # Explained once at the top of the Markdown reference.


def build_markdown(spec: dict[str, Any] | None = None) -> str:
    spec = spec or build_openapi()
    lines = [
        "# PHFrame HTTP API reference",
        "",
        "<!-- Generated by `python -m public_health_framework.http_reference --write docs`; do not edit by hand. -->",
        "",
        f"Version {spec['info']['version']} · OpenAPI {spec['openapi']} document: [`openapi.json`](openapi.json), "
        "also served by every application at `/api/openapi.json`.",
        "",
        spec["info"]["description"],
        "",
        "Every response may also be `429` when a client exceeds the rate limit (`PHFRAME_RATE_LIMIT` requests per minute, "
        "10 per minute for sign-in) or `413` when the body exceeds `PHFRAME_MAX_BODY_BYTES`. Session-protected `/api` routes "
        "return `401` and pages redirect to `/login` when the application is private.",
        "",
        "## Contents",
        "",
    ]
    by_tag: dict[str, list[tuple[str, str, dict[str, Any]]]] = {name: [] for name, _ in TAGS}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            by_tag[operation["tags"][0]].append((method.upper(), path, operation))
    for name, description in TAGS:
        lines.append(f"- [{name}](#{name.lower()}): {description}")
    lines.append("- [Schemas](#schemas)")
    lines.append("")
    for name, description in TAGS:
        lines += [f"## {name}", "", description, ""]
        for method, path, operation in by_tag[name]:
            lines += [f"### `{method} {path}`", "", f"**{operation['summary']}.**" + (" " + operation["description"] if "description" in operation else ""), ""]
            if operation.get("security") == []:
                lines += ["No session required.", ""]
            parameters = operation.get("parameters", [])
            if parameters:
                lines += ["| Parameter | In | Type | Description |", "|---|---|---|---|"]
                for parameter in parameters:
                    lines.append(f"| `{parameter['name']}` | {parameter['in']} | {_cell(_type(parameter['schema']))} | {_cell(parameter.get('description', ''))} |")
                lines.append("")
            if "requestBody" in operation:
                media, content = next(iter(operation["requestBody"]["content"].items()))
                optional = "" if operation["requestBody"]["required"] else " (optional)"
                lines += [f"Request body{optional}: `{media}`, {_type(content['schema'])}.", ""]
            lines += ["| Status | Description | Body |", "|---|---|---|"]
            for status, response in operation["responses"].items():
                if response["description"] in _COMMON:
                    continue
                content = response.get("content", {})
                body = "; ".join(f"`{media}` {_type(value['schema'])}" for media, value in content.items()) or "—"
                lines.append(f"| {status} | {_cell(response['description'])} | {_cell(body)} |")
            lines.append("")
    lines += ["## Schemas", "", "Responses may gain fields in minor releases; clients should ignore fields they do not know.", ""]
    for name, schema in spec["components"]["schemas"].items():
        lines += [f"### {name}", ""] + _fields(schema)
    return "\n".join(lines).rstrip() + "\n"


def write(directory: Path) -> None:
    spec = build_openapi()
    (directory / "openapi.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (directory / "http-api.md").write_text(build_markdown(spec), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Print or write the PHFrame HTTP API reference.")
    parser.add_argument("--write", metavar="DIRECTORY", help="Write openapi.json and http-api.md into this directory.")
    parser.add_argument("--markdown", action="store_true", help="Print the Markdown reference instead of the OpenAPI document.")
    arguments = parser.parse_args()
    if arguments.write:
        write(Path(arguments.write))
    elif arguments.markdown:
        print(build_markdown(), end="")
    else:
        print(json.dumps(build_openapi(), indent=2))


if __name__ == "__main__":
    main()
