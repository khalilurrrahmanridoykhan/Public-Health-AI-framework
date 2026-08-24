"""Connector registry and secure JSON transport for public-health systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import json
import os
from typing import Any, Callable
from urllib.parse import urlencode
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
    request = Request(url, headers={"accept": "application/json", **headers})
    with urlopen(request, timeout=timeout) as response:
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
        payload = self.transport(self.endpoint(), self.headers(), self.config.timeout)
        return [self.map_record(record) for record in self.extract(payload)]

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
