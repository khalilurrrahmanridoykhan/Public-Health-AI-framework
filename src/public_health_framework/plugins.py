"""Small, stable plugin hooks for the Phase 1 application lifecycle."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
import re
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

def installed_plugins() -> dict[str, object]:
    return {item.name: item.load() for item in entry_points(group="phframe.plugins")}

def create_plugin(name: str, directory: str | Path | None = None) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"); module = slug.replace("-", "_")
    if not slug: raise ValueError("Plugin name must contain letters or numbers.")
    root = Path(directory or f"phframe-{slug}").resolve()
    if root.exists(): raise FileExistsError(f"Plugin directory already exists: {root}")
    package = root / "src" / f"phframe_{module}"; package.mkdir(parents=True); (root / "tests").mkdir()
    (package / "__init__.py").write_text('def setup(app, config):\n    """Register routes, lifecycle hooks, or components."""\n', encoding="utf-8")
    (root / "pyproject.toml").write_text(f'''[build-system]\nrequires = ["setuptools>=69"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = "phframe-{slug}"\nversion = "0.1.0"\ndependencies = ["public-health-framework>=0.8"]\n\n[project.entry-points."phframe.plugins"]\n{slug} = "phframe_{module}"\n''', encoding="utf-8")
    (root / "README.md").write_text(f"# PHFrame {name} plugin\n\nAdd `phframe_{module}` to the project's `plugins` list.\n", encoding="utf-8")
    (root / "tests" / "test_plugin.py").write_text(f"from phframe_{module} import setup\n\ndef test_setup_exists():\n    assert callable(setup)\n", encoding="utf-8")
    return root
