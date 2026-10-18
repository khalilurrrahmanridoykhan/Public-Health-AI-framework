import json
from pathlib import Path

import pytest

from public_health_framework.cli import main
from public_health_framework.config import ProjectConfig
from public_health_framework.project import create_project
from public_health_framework.settings import SiteSettings
from public_health_framework.upgrade import upgrade_project


def legacy_project(tmp_path: Path, name: str) -> Path:
    """A 0.9 preview project: unversioned phframe.yaml and pre-Phase-7 settings."""
    root = create_project(name, tmp_path / name)
    config_path = root / "phframe.yaml"
    text = config_path.read_text(encoding="utf-8")
    assert text.startswith("version: 1\n\n")
    config_path.write_text(text[len("version: 1\n\n") :], encoding="utf-8")
    settings_path = root / "data" / "phframe-settings.json"
    settings_path.write_text(json.dumps({
        "footer_text": "Powered by PHFrame",
        "dashboards": [{
            "id": "main", "title": "Main", "description": "", "dataset": "case_reports",
            "template": "overview", "widgets": [{"_id": "kpi-1", "type": "kpi", "title": "Total cases", "indicator": "total_cases"}],
        }],
    }), encoding="utf-8")
    return root


def test_check_mode_reports_pending_upgrades_without_writing(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-check")
    config_path = root / "phframe.yaml"
    settings_path = root / "data" / "phframe-settings.json"
    before_config, before_settings = config_path.read_text(encoding="utf-8"), settings_path.read_text(encoding="utf-8")
    actions = upgrade_project(config_path, check_only=True)
    assert "add 'version: 1' to phframe.yaml" in actions
    assert "update data/phframe-settings.json to the current dashboard and footer format" in actions
    assert config_path.read_text(encoding="utf-8") == before_config
    assert settings_path.read_text(encoding="utf-8") == before_settings


def test_upgrade_adds_config_version_and_preserves_the_rest_of_the_file(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-version")
    config_path = root / "phframe.yaml"
    original = config_path.read_text(encoding="utf-8")
    upgrade_project(config_path)
    upgraded = config_path.read_text(encoding="utf-8")
    assert upgraded == f"version: 1\n\n{original}"
    assert ProjectConfig.load(config_path).version == 1


def test_upgrade_merges_legacy_single_dataset_dashboards_into_a_datasets_list(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-dashboard")
    upgrade_project(root / "phframe.yaml")
    settings = SiteSettings(root, "Preview Dashboard").load()
    dashboard = settings["dashboards"][0]
    assert dashboard["datasets"] == ["case_reports"]
    assert dashboard["dataset"] == "case_reports"  # the legacy key is kept, not dropped


def test_upgrade_merges_legacy_footer_text(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-footer")
    upgrade_project(root / "phframe.yaml")
    stored = json.loads((root / "data" / "phframe-settings.json").read_text(encoding="utf-8"))
    assert stored["footer_html"] == "<p>Powered by PHFrame</p>"


def test_upgrade_is_idempotent(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-idempotent")
    config_path = root / "phframe.yaml"
    upgrade_project(config_path)
    settings_path = root / "data" / "phframe-settings.json"
    after_first = (config_path.read_text(encoding="utf-8"), settings_path.read_text(encoding="utf-8"))
    assert upgrade_project(config_path) == []
    assert (config_path.read_text(encoding="utf-8"), settings_path.read_text(encoding="utf-8")) == after_first


def test_upgrade_refuses_a_config_that_cannot_be_validated_automatically(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-invalid")
    config_path = root / "phframe.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("required: true", "requird: true"), encoding="utf-8"
    )
    original = config_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="unknown key; did you mean 'required'"):
        upgrade_project(config_path)
    assert config_path.read_text(encoding="utf-8") == original


def test_cli_upgrade_check_then_apply(tmp_path: Path):
    root = legacy_project(tmp_path, "preview-cli")
    config_path = str(root / "phframe.yaml")
    assert main(["upgrade", "--check", "--config", config_path]) == 1
    assert main(["upgrade", "--config", config_path]) == 0
    assert main(["upgrade", "--config", config_path]) == 0


def test_already_upgraded_project_has_nothing_pending(tmp_path: Path):
    root = create_project("Already Current", tmp_path / "already-current")
    assert upgrade_project(root / "phframe.yaml", check_only=True) == []
