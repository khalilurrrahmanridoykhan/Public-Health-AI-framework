"""Connector synchronization orchestration and due-schedule evaluation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from .config import ProjectConfig
from .connectors import Transport, create_connector, json_transport
from .importer import import_frame, stage_frame
from .storage import Storage


@dataclass(frozen=True)
class SyncResult:
    run_id: int
    connector: str
    dataset: str
    status: str
    fetched_rows: int
    imported_rows: int
    errors: tuple[dict[str, Any], ...]
    dry_run: bool = False
    version_id: int | None = None


def sync_connector(
    config: ProjectConfig, name: str, dry_run: bool = False,
    transport: Transport = json_transport,
) -> SyncResult:
    if name not in config.connectors:
        raise ValueError(f"Connector not found: {name}")
    connector_config = config.connectors[name]
    if connector_config.type == "dhis2" and connector_config.token_env == "PHFRAME_DHIS2_OAUTH_TOKEN":
        from .dhis2_oauth import DHIS2OAuth
        DHIS2OAuth(config.root).access_token(connector_config.base_url)
    if connector_config.type == "dhis2" and connector_config.username_env == "PHFRAME_DHIS2_BASIC_USERNAME":
        from .dhis2_oauth import DHIS2OAuth
        DHIS2OAuth(config.root).basic_credentials(connector_config.base_url)
    if connector_config.type == "dhis2" and not connector_config.parameters.get("period"):
        from .dhis2_oauth import DHIS2OAuth
        connector_config = replace(connector_config, parameters=DHIS2OAuth(config.root).data_set_sync_parameters(connector_config.resource))
    storage = Storage(config)
    storage.initialize()
    fetched = imported = 0
    version_id: int | None = None
    errors: list[dict[str, Any]] = []
    status = "failed"
    try:
        records = create_connector(connector_config, transport).pull()
        fetched = len(records)
        if not records:
            status = "validated" if dry_run else "completed"
        else:
            frame = pd.DataFrame(records)
            version = stage_frame(config, connector_config.dataset, frame, f"connector:{name}", connector_config.type)
            version_id = int(version["id"])
            result = import_frame(
                config, connector_config.dataset, frame,
                f"connector:{name}", mapping=None, dry_run=dry_run,
            )
            imported = result.imported_rows
            errors = list(result.errors)
            status = result.status
            if not dry_run and not errors:
                storage.approve_dataset_version(version_id)
    except (OSError, ValueError) as error:
        errors.append({"message": str(error)})
    run_id = storage.record_sync(name, connector_config.dataset, status, fetched, imported, errors)
    return SyncResult(run_id, name, connector_config.dataset, status, fetched, imported, tuple(errors), dry_run, version_id)


def connector_due(config: ProjectConfig, name: str, now: datetime | None = None) -> bool:
    connector = config.connectors[name]
    if connector.schedule_minutes is None:
        return False
    storage = Storage(config)
    storage.initialize()
    history = storage.sync_history(1, name)
    if not history:
        return True
    last = datetime.fromisoformat(history[0]["created_at"])
    current = now or datetime.now().astimezone()
    if last.tzinfo is None:
        last = last.replace(tzinfo=current.tzinfo)
    return current >= last + timedelta(minutes=connector.schedule_minutes)
