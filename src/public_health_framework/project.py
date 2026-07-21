"""Create and validate PHFrame projects."""

from __future__ import annotations

from pathlib import Path
import re

from .config import ProjectConfig
from .storage import Storage


PROJECT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]*$")

CONFIG_TEMPLATE = """project:
  name: "{title}"
  database: sqlite:///data/phframe.db

datasets:
  case_reports:
    label: Case Reports
    fields:
      case_id:
        type: string
        required: true
        protected: true
      disease:
        type: string
        required: true
      status:
        type: string
        required: true
      onset_date:
        type: date
      report_date:
        type: date
        required: true
      district:
        type: location
        required: true
      cases:
        type: integer
        required: true
      population:
        type: integer

plugins: []
"""

README_TEMPLATE = """# {title}

This public-health application was created with PHFrame.

## Run

```bash
phframe check
phframe serve
```

Open <http://127.0.0.1:8000> and inspect API metadata at
<http://127.0.0.1:8000/api>.

Edit `phframe.yaml` to customize datasets and fields.
"""

GITIGNORE_TEMPLATE = """__pycache__/
*.py[cod]
.env
data/*.db
data/*.db-*
"""


def create_project(name: str, directory: str | Path | None = None) -> Path:
    if not PROJECT_NAME.fullmatch(name):
        raise ValueError("Project name must start with a letter and contain letters, numbers, spaces, - or _.")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    root = Path(directory or slug).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "plugins").mkdir(exist_ok=True)
    (root / "phframe.yaml").write_text(CONFIG_TEMPLATE.format(title=name), encoding="utf-8")
    (root / "README.md").write_text(README_TEMPLATE.format(title=name), encoding="utf-8")
    (root / ".gitignore").write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
    (root / "plugins" / "__init__.py").write_text('"""Local PHFrame plugins."""\n', encoding="utf-8")
    config = ProjectConfig.load(root / "phframe.yaml")
    Storage(config).initialize()
    return root


def check_project(config_path: str | Path = "phframe.yaml") -> tuple[ProjectConfig, list[str]]:
    config = ProjectConfig.load(config_path)
    messages = [f"Configuration: {Path(config_path).resolve()}"]
    messages.append(f"Project: {config.name}")
    messages.append(f"Datasets: {len(config.datasets)}")
    messages.append(f"Database: {config.database_path}")
    Storage(config).initialize()
    messages.append("Database: ready")
    messages.append("System check passed")
    return config, messages

