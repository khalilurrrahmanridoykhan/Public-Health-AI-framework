"""Upgrade a 0.9 preview project to the 1.0 configuration, settings, and database shape."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .config import ProjectConfig
from .config_schema import CONFIG_VERSION, validate_config
from .settings import SiteSettings, migrate_settings
from .storage import Storage


def upgrade_project(config_path: str | Path = "phframe.yaml", check_only: bool = False) -> list[str]:
    """Report, and unless check_only, apply every automatic 1.0 upgrade step."""
    path = Path(config_path).resolve()
    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    actions: list[str] = []

    if "version" not in raw:
        issues = validate_config({"version": CONFIG_VERSION, **raw})
        if issues:
            listed = "\n".join(f"  - {issue}" for issue in issues[:20])
            raise ValueError(
                "phframe.yaml cannot be upgraded to version 1 automatically; fix these issues, "
                f"then rerun `phframe upgrade`:\n{listed}"
            )
        actions.append(f"add 'version: {CONFIG_VERSION}' to phframe.yaml")
        if not check_only:
            path.write_text(f"version: {CONFIG_VERSION}\n\n{raw_text}", encoding="utf-8")

    config = ProjectConfig.load(config_path)
    settings = SiteSettings(config.root, config.name)
    if settings.path.exists():
        stored = json.loads(settings.path.read_text(encoding="utf-8"))
        if migrate_settings(stored) != stored:
            actions.append("update data/phframe-settings.json to the current dashboard and footer format")
            if not check_only:
                settings.upgrade()

    actions.extend(f"database: {item}" for item in Storage(config).migrate(check_only=check_only))
    return actions
