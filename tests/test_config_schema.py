import json
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.config_schema import (
    CONFIG_VERSION, build_markdown, build_schema, validate_config, validate_section,
)
from public_health_framework.project import CONFIG_TEMPLATE, check_project, create_project

DOCS = Path(__file__).resolve().parents[1] / "docs"
REGENERATE = "python -m public_health_framework.config_schema --write docs"


def template() -> dict:
    return yaml.safe_load(CONFIG_TEMPLATE.format(title="Schema Test"))


def write(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "phframe.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def messages(raw: dict) -> list[str]:
    return [str(issue) for issue in validate_config(raw)]


def test_generated_reference_is_current():
    schema = build_schema()
    assert json.loads((DOCS / "phframe.schema.json").read_text(encoding="utf-8")) == schema, f"Regenerate with `{REGENERATE}`."
    assert (DOCS / "configuration.md").read_text(encoding="utf-8") == build_markdown(schema), f"Regenerate with `{REGENERATE}`."


def test_schema_is_valid_json_schema_and_agrees_with_builtin_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = build_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    valid = template()
    invalid = template()
    invalid["server"]["port"] = 70000
    invalid["indicators"]["total_cases"].pop("field")
    invalid["datasets"]["case_reports"]["fields"]["cases"]["requird"] = True
    for raw in (valid, invalid):
        assert bool(list(validator.iter_errors(raw))) == bool(validate_config(raw))


def test_generated_project_declares_current_version_and_matches_schema(tmp_path: Path):
    raw = template()
    assert raw["version"] == CONFIG_VERSION
    assert validate_config(raw) == []
    root = create_project("Schema Project", tmp_path / "schema-project")
    config, report = check_project(root / "phframe.yaml")
    assert config.version == CONFIG_VERSION and config.warnings == ()
    assert "Configuration version: 1" in report
    assert not any(line.startswith("Warning:") for line in report)


def test_versioned_file_rejects_unknown_keys_with_suggestion(tmp_path: Path):
    raw = template()
    raw["datasets"]["case_reports"]["fields"]["cases"]["requird"] = True
    raw["dashbords"] = {}
    with pytest.raises(ValueError) as error:
        ProjectConfig.load(write(tmp_path, raw))
    text = str(error.value)
    assert "datasets.case_reports.fields.cases.requird: unknown key; did you mean 'required'?" in text
    assert "dashbords: unknown key; did you mean 'dashboards'?" in text


@pytest.mark.parametrize(("change", "expected"), [
    (lambda raw: raw["server"].update(port="eighty"), "server.port: expected integer, got string"),
    (lambda raw: raw["server"].update(port=0), "server.port: must be at least 1"),
    (lambda raw: raw["ui"].update(theme="neon"), "ui.theme: must be one of light, dark, high-contrast"),
    (lambda raw: raw["indicators"]["total_cases"].pop("field"), "indicators.total_cases: missing required key 'field'"),
    (lambda raw: raw["data_quality"]["cases_nonnegative"].pop("min"), "data_quality.cases_nonnegative: missing required key"),
    (lambda raw: raw["dashboards"]["main"]["widgets"].append({"type": "kpi"}), "dashboards.main.widgets[5]: missing required key 'indicator'"),
    (lambda raw: raw["datasets"]["case_reports"]["fields"].update(status="text"), "datasets.case_reports.fields.status: must be one of"),
    (lambda raw: raw["datasets"].update(CaseReports={"fields": {"id": "string"}}), "datasets.CaseReports: invalid name"),
    (lambda raw: raw["project"].pop("name"), "project: missing required key 'name'"),
])
def test_schema_reports_the_offending_key(change, expected):
    raw = template()
    change(raw)
    assert any(expected in message for message in messages(raw)), messages(raw)


def test_unsupported_version_is_rejected(tmp_path: Path):
    raw = template()
    raw["version"] = 2
    with pytest.raises(ValueError, match="Unsupported configuration version 2"):
        ProjectConfig.load(write(tmp_path, raw))


def test_unversioned_preview_file_loads_with_warnings(tmp_path: Path):
    raw = template()
    raw.pop("version")
    raw["datasets"]["case_reports"]["fields"]["cases"]["requird"] = True
    path = write(tmp_path, raw)
    config = ProjectConfig.load(path)
    assert config.version is None
    assert config.warnings == ("datasets.case_reports.fields.cases.requird: unknown key; did you mean 'required'?",)
    _, report = check_project(path)
    assert "Configuration version: none (0.9 preview format)" in report
    assert "Warning: datasets.case_reports.fields.cases.requird: unknown key; did you mean 'required'?" in report


def test_connectors_are_validated_before_they_are_saved(tmp_path: Path):
    root = create_project("Connector Schema", tmp_path / "connector-schema")
    path = root / "phframe.yaml"
    before = path.read_text(encoding="utf-8")
    client = TestClient(PHFrame.from_file(str(path)).asgi)
    payload = {
        "name": "surveillance", "type": "api", "dataset": "case_reports", "base_url": "https://example.org",
        "resource": "cases", "mapping": {"id": "case_id"}, "schedul_minutes": 5,
    }
    response = client.post("/api/connectors", json=payload)
    assert response.status_code == 422
    assert "connectors.surveillance.schedul_minutes: unknown key" in response.json()["error"]["message"]
    assert path.read_text(encoding="utf-8") == before
    payload["schedule_minutes"] = payload.pop("schedul_minutes")
    assert client.post("/api/connectors", json=payload).status_code == 201
    assert ProjectConfig.load(path).connectors["surveillance"].schedule_minutes == 5
    assert validate_section("connectors", "surveillance", {k: v for k, v in payload.items() if k != "name"}) == []


def test_reference_documents_every_section_and_definition():
    schema = build_schema()
    reference = build_markdown(schema)
    for section in schema["properties"]:
        assert f"| `{section}` |" in reference
    for name in schema["$defs"]:
        assert f"### {name}" in reference
