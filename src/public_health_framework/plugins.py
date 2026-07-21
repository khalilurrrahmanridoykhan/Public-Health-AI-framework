"""Small, stable plugin hooks for the Phase 1 application lifecycle."""

from __future__ import annotations

from importlib import import_module
from typing import Protocol

from .config import ProjectConfig


class Plugin(Protocol):
    def setup(self, app: object, config: ProjectConfig) -> None: ...


def load_plugins(names: tuple[str, ...], app: object, config: ProjectConfig) -> None:
    for name in names:
        module_name, separator, attribute = name.partition(":")
        module = import_module(module_name)
        plugin = getattr(module, attribute) if separator else module
        setup = getattr(plugin, "setup", None)
        if not callable(setup):
            raise ValueError(f"Plugin '{name}' must provide setup(app, config).")
        setup(app, config)

