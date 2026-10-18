"""Machine-readable description of the PHFrame public API surface.

The contract lists the Python exports, command-line commands and options, HTTP
routes, and plugin entry-point group that PHFrame promises to keep stable
within a major version. ``docs/public-api-contract.json`` stores the reviewed
snapshot; the test suite fails when the live surface drifts from it.

Regenerate the snapshot after an intentional change with::

    python -m public_health_framework.contract > docs/public-api-contract.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from starlette.routing import Route

CONTRACT_VERSION = 1
PLUGIN_ENTRY_POINT_GROUP = "phframe.plugins"


def python_surface() -> list[str]:
    import public_health_framework

    return sorted(public_health_framework.__all__)


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _options(parser: argparse.ArgumentParser) -> list[str]:
    names: list[str] = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        names.extend(action.option_strings or [f"<{action.dest}>"])
    return sorted(names)


def cli_surface() -> dict[str, list[str]]:
    from .cli import _parser

    commands: dict[str, list[str]] = {}

    def visit(parser: argparse.ArgumentParser, prefix: str) -> None:
        for name, child in _subcommands(parser).items():
            command = f"{prefix} {name}".strip()
            commands[command] = _options(child)
            visit(child, command)

    visit(_parser(), "")
    return dict(sorted(commands.items()))


def http_surface(app: Any) -> list[dict[str, Any]]:
    routes = []
    for route in app.asgi.routes:
        if isinstance(route, Route):
            methods = sorted((route.methods or set()) - {"HEAD"})
            routes.append({"path": route.path, "methods": methods})
    return sorted(routes, key=lambda item: item["path"])


def build_contract(app: Any) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "python": python_surface(),
        "cli": cli_surface(),
        "http": http_surface(app),
        "plugins": {"entry_point_group": PLUGIN_ENTRY_POINT_GROUP, "hook": "setup(app, config)"},
    }


def framework_contract() -> dict[str, Any]:
    """Build the contract for a default project with no plugins installed."""
    from .application import PHFrame
    from .project import create_project

    with tempfile.TemporaryDirectory() as directory:
        root = create_project("Contract Reference", Path(directory) / "contract-reference")
        return build_contract(PHFrame.from_file(str(root / "phframe.yaml")))


def compare_contracts(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, list[str]]:
    """Return removed (breaking) and added (additive) surface items."""

    def flatten(contract: dict[str, Any]) -> set[str]:
        items = {f"python:{name}" for name in contract.get("python", [])}
        for command, options in contract.get("cli", {}).items():
            items.add(f"cli:{command}")
            items.update(f"cli:{command} {option}" for option in options)
        for route in contract.get("http", []):
            items.update(f"http:{method} {route['path']}" for method in route["methods"])
        plugins = contract.get("plugins", {})
        items.update(f"plugins:{key}={value}" for key, value in plugins.items())
        return items

    before, after = flatten(expected), flatten(actual)
    return {"removed": sorted(before - after), "added": sorted(after - before)}


def main() -> None:
    print(json.dumps(framework_contract(), indent=2))


if __name__ == "__main__":
    main()
