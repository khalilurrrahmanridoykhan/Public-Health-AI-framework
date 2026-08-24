"""PHFrame ASGI application and automatically generated dataset APIs."""

from __future__ import annotations

from html import escape
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from . import __version__
from .config import DatasetSchema, ProjectConfig
from .plugins import load_plugins
from .periods import resolve_period
from .storage import Storage
from .ui import asset_text


class PHFrame:
    """A public-health application created from a PHFrame project configuration."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.storage = Storage(config)
        self.storage.initialize()
        routes = [
            Route("/", self.home, methods=["GET"]),
            Route("/app", self.frontend, methods=["GET"]),
            Route("/assets/phframe.css", self.frontend_css, methods=["GET"]),
            Route("/assets/phframe.js", self.frontend_js, methods=["GET"]),
            Route("/health", self.health, methods=["GET"]),
            Route("/api", self.api_index, methods=["GET"]),
            Route("/api/imports", self.import_history, methods=["GET"]),
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
            Route("/api/{dataset}", self.collection, methods=["GET", "POST"]),
            Route("/api/{dataset}/{record_id:int}", self.detail, methods=["GET", "PUT", "PATCH", "DELETE"]),
        ]
        self.asgi = Starlette(debug=False, routes=routes)
        self.asgi.state.phframe = self
        load_plugins(config.plugins, self.asgi, config)

    @classmethod
    def from_file(cls, path: str = "phframe.yaml") -> "PHFrame":
        return cls(ProjectConfig.load(path))

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        await self.asgi(scope, receive, send)

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
<p><a href="/api">API metadata</a> · <a href="/health">Health check</a></p></body></html>"""
        return HTMLResponse(html)

    async def health(self, request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "framework": "PHFrame", "version": __version__, "project": self.config.name})

    async def frontend(self, request: Request) -> HTMLResponse:
        return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PHFrame</title>
<link rel="stylesheet" href="/assets/phframe.css"></head><body><ph-app-shell></ph-app-shell>
<noscript>PHFrame requires JavaScript for the application interface. Dataset APIs remain available at /api.</noscript>
<script type="module" src="/assets/phframe.js"></script></body></html>""")

    async def frontend_css(self, request: Request) -> Response:
        return Response(asset_text("phframe.css"), media_type="text/css")

    async def frontend_js(self, request: Request) -> Response:
        return Response(asset_text("phframe.js"), media_type="text/javascript")

    async def api_index(self, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "project": self.config.name,
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

    async def import_history(self, request: Request) -> JSONResponse:
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            return _error("limit must be an integer.", 400)
        return JSONResponse({"data": self.storage.import_history(limit)})

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
                records = self.storage.list(dataset, limit, offset, filters)
            except ValueError as error:
                return _error(str(error), 422)
            return JSONResponse({"data": records, "count": len(records), "limit": limit, "offset": offset})
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
