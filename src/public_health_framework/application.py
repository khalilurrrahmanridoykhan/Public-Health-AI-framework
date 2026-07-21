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
from .storage import Storage


class PHFrame:
    """A public-health application created from a PHFrame project configuration."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.storage = Storage(config)
        self.storage.initialize()
        routes = [
            Route("/", self.home, methods=["GET"]),
            Route("/health", self.health, methods=["GET"]),
            Route("/api", self.api_index, methods=["GET"]),
            Route("/api/imports", self.import_history, methods=["GET"]),
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
            }
        )

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
            except ValueError:
                return _error("limit and offset must be integers.", 400)
            records = self.storage.list(dataset, limit, offset)
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
