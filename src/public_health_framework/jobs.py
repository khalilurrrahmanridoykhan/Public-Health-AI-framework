"""Small production worker for scheduled connector jobs."""
from __future__ import annotations
from dataclasses import asdict
import logging
import time
from typing import Any
from .sync import connector_due, sync_connector

log = logging.getLogger("phframe.worker")

def run_due(config: Any, retries: int = 2) -> list[dict[str, Any]]:
    results = []
    for name in config.connectors:
        if not connector_due(config, name): continue
        for attempt in range(retries + 1):
            try:
                item = asdict(sync_connector(config, name)); item["attempts"] = attempt + 1; results.append(item); break
            except Exception as error:
                if attempt == retries: results.append({"connector": name, "status": "failed", "attempts": attempt + 1, "error": str(error)})
                else: time.sleep(min(2 ** attempt, 5))
    return results

def work(config: Any, interval: int = 60, once: bool = False) -> None:
    while True:
        for result in run_due(config): log.info("connector job", extra={"phframe": result})
        if once: return
        time.sleep(max(5, interval))
