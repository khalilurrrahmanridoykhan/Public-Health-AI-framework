from pathlib import Path

import pytest

from public_health_framework.config import ConnectorSchema, ProjectConfig
from public_health_framework.connectors import Connector, create_connector, register_connector
from public_health_framework.project import create_project


@register_connector("test_connector")
class DummyConnector(Connector):
    def endpoint(self):
        return self.url("records", {"page": "1"})

    def extract(self, payload):
        return payload["records"]


def _schema(**changes):
    values = dict(
        name="test", type="test_connector", dataset="case_reports",
        base_url="https://example.test", resource="records",
        mapping={"source.id": "case_id"}, parameters={"limit": "10"}, timeout=30,
    )
    values.update(changes)
    return ConnectorSchema(**values)


def test_connector_transport_auth_and_nested_mapping(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "secret-token")
    calls = []
    connector = create_connector(
        _schema(token_env="TEST_TOKEN"),
        lambda url, headers, timeout: calls.append((url, headers, timeout)) or {"records": [{"source": {"id": "M-1"}}]},
    )
    assert connector.pull() == [{"case_id": "M-1"}]
    assert calls[0][0] == "https://example.test/records?limit=10&page=1"
    assert calls[0][1] == {"authorization": "Bearer secret-token"}
    assert calls[0][2] == 30


def test_connector_requires_credential_environment(monkeypatch):
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    with pytest.raises(ValueError, match="MISSING_TOKEN"):
        create_connector(_schema(token_env="MISSING_TOKEN")).headers()


def test_project_connector_configuration_validation(tmp_path: Path):
    root = create_project("Connector Config", tmp_path / "connector-config")
    path = root / "phframe.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "connectors: {}",
        """connectors:
  surveillance:
    type: dhis2
    dataset: case_reports
    base_url: https://dhis.example
    resource: malaria
    mapping:
      id: case_id
    auth:
      token_env: DHIS_TOKEN""",
    ), encoding="utf-8")
    connector = ProjectConfig.load(path).connectors["surveillance"]
    assert connector.type == "dhis2"
    assert connector.token_env == "DHIS_TOKEN"
