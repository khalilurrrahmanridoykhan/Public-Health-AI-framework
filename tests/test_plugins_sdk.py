from pathlib import Path
from public_health_framework.plugins import create_plugin

def test_plugin_scaffold(tmp_path: Path):
    root = create_plugin("Malaria Tools", tmp_path / "plugin")
    assert (root / "pyproject.toml").exists()
    assert '"phframe.plugins"' in (root / "pyproject.toml").read_text()
    assert (root / "src" / "phframe_malaria_tools" / "__init__.py").exists()
