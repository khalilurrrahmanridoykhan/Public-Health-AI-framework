"""Connector registry and secure JSON transport for public-health systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import json
import os
from typing import Any, Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .config import ConnectorSchema


Transport = Callable[[str, dict[str, str], int], Any]
CONNECTORS: dict[str, type["Connector"]] = {}


def register_connector(name: str):
    def decorator(connector: type["Connector"]) -> type["Connector"]:
        CONNECTORS[name] = connector
        return connector
    return decorator


def json_transport(url: str, headers: dict[str, str], timeout: int) -> Any:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Connector URL must use HTTP or HTTPS.")
    request = Request(url, headers={"accept": "application/json", **headers})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - scheme and host validated above
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


class Connector(ABC):
    def __init__(self, config: ConnectorSchema, transport: Transport = json_transport):
        self.config = config
        self.transport = transport

    @abstractmethod
    def endpoint(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract(self, payload: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def pull(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        url: str | None = self.endpoint()
        pages = 0
        while url:
            payload = self.transport(url, self.headers(), self.config.timeout)
            records.extend(self.map_record(record) for record in self.extract(payload))
            url = self.next_page(payload)
            pages += 1
            if pages >= 100 and url:
                raise ValueError(f"Connector '{self.config.name}' exceeded the 100-page safety limit.")
        return records

    def next_page(self, payload: Any) -> str | None:
        return None

    def headers(self) -> dict[str, str]:
        if self.config.token_env:
            token = _required_env(self.config.token_env)
            return {"authorization": f"Bearer {token}"}
        if self.config.username_env or self.config.password_env:
            if not self.config.username_env or not self.config.password_env:
                raise ValueError(f"Connector '{self.config.name}' basic auth requires username_env and password_env.")
            credentials = f"{_required_env(self.config.username_env)}:{_required_env(self.config.password_env)}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"authorization": f"Basic {encoded}"}
        return {}

    def url(self, path: str, parameters: dict[str, str] | None = None) -> str:
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        query = {**self.config.parameters, **(parameters or {})}
        return f"{url}?{urlencode(query)}" if query else url

    def map_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            target: _nested_value(record, source)
            for source, target in self.config.mapping.items()
        }


def create_connector(config: ConnectorSchema, transport: Transport = json_transport) -> Connector:
    connector = CONNECTORS.get(config.type)
    if connector is None:
        raise ValueError(f"Connector type is not registered: {config.type}")
    return connector(config, transport)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required connector credential environment variable is not set: {name}")
    return value


def _nested_value(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


@register_connector("api")
class APIConnector(Connector):
    """Pull records from a generic JSON REST API."""

    def endpoint(self) -> str:
        return self.url(self.config.resource)

    def extract(self, payload: Any) -> list[dict[str, Any]]:
        value = payload
        if self.config.records_path:
            value = _nested_value(payload, self.config.records_path) if isinstance(payload, dict) else None
        elif isinstance(payload, dict):
            for key in ("data", "records", "results", "items", "value"):
                if isinstance(payload.get(key), list):
                    value = payload[key]
                    break
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError("API response must be a JSON list of objects or contain data, records, results, items, or value.")
        return value

    def next_page(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("next") or payload.get("next_url")
        return str(value) if value else None


@register_connector("dhis2")
class DHIS2Connector(Connector):
    """Pull data values from the DHIS2 Web API."""

    def endpoint(self) -> str:
        return self.url("api/dataValueSets", {"dataSet": self.config.resource})

    def headers(self) -> dict[str, str]:
        if self.config.token_env:
            scheme = "Bearer" if self.config.token_env == "PHFRAME_DHIS2_OAUTH_TOKEN" else "ApiToken"
            return {"authorization": f"{scheme} {_required_env(self.config.token_env)}"}
        return super().headers()

    def extract(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("dataValues"), list):
            raise ValueError("DHIS2 response must contain a dataValues list.")
        return payload["dataValues"]


@register_connector("kobo")
class KoboConnector(Connector):
    """Pull submissions from the KoboToolbox v2 API."""

    def endpoint(self) -> str:
        return self.url(f"api/v2/assets/{self.config.resource}/data/")

    def headers(self) -> dict[str, str]:
        if self.config.token_env:
            return {"authorization": f"Token {_required_env(self.config.token_env)}"}
        return super().headers()

    def extract(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Kobo response must contain a results list.")
        return payload["results"]

    def next_page(self, payload: Any) -> str | None:
        value = payload.get("next") if isinstance(payload, dict) else None
        return str(value) if value else None


@register_connector("odk")
class ODKConnector(Connector):
    """Pull submissions from an ODK Central OData endpoint."""

    def endpoint(self) -> str:
        parts = self.config.resource.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError("ODK connector resource must use PROJECT_ID/FORM_ID format.")
        project, form = parts
        return self.url(f"v1/projects/{project}/forms/{form}.svc/Submissions")

    def extract(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise ValueError("ODK response must contain a value list.")
        return payload["value"]

    def next_page(self, payload: Any) -> str | None:
        value = payload.get("@odata.nextLink") if isinstance(payload, dict) else None
        return str(value) if value else None
