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
  environment: development

server:
  host: 127.0.0.1
  port: 8000

datasets:
  case_reports:
    label: Case Reports
    fields:
      case_id:
        type: identifier
        required: true
        protected: true
      disease:
        type: disease_code
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
      patient_age:
        type: age
      epi_week:
        type: epi_week
      reporting_unit:
        type: organisation_unit

indicators:
  total_cases:
    label: Total Cases
    dataset: case_reports
    operation: sum
    field: cases
    date_field: report_date
  incidence_per_100000:
    label: Incidence per 100,000
    dataset: case_reports
    operation: rate
    numerator: cases
    denominator: population
    multiplier: 100000
    date_field: report_date

data_quality:
  cases_nonnegative:
    label: Cases are nonnegative
    dataset: case_reports
    field: cases
    check: range
    min: 0
  valid_case_status:
    label: Case status is recognized
    dataset: case_reports
    field: status
    check: allowed
    values: [suspected, probable, confirmed]

filters:
  confirmed_cases:
    label: Confirmed cases
    dataset: case_reports
    values:
      status: confirmed

dimensions:
  cases_by_district:
    label: Cases by district
    dataset: case_reports
    field: district
  confirmed_cases_by_district:
    label: Confirmed cases by district
    dataset: case_reports
    field: district
    filter: confirmed_cases

thresholds:
  high_weekly_case_count:
    label: High weekly case count
    indicator: total_cases
    operator: gte
    value: 10
    severity: warning
    message: Weekly case count has reached the surveillance alert level.

organisation_units:
  bangladesh:
    name: Bangladesh
    level: country
  chattogram_division:
    name: Chattogram Division
    level: division
    parent: bangladesh
  bandarban:
    name: Bandarban
    level: district
    parent: chattogram_division
  rangamati:
    name: Rangamati
    level: district
    parent: chattogram_division

dashboards:
  main:
    label: Malaria Surveillance Dashboard
    widgets:
      - type: kpi
        title: Total cases
        indicator: total_cases
      - type: kpi
        title: Incidence per 100,000
        indicator: incidence_per_100000
      - type: chart
        title: Cases by district
        dimension: cases_by_district
      - type: map
        title: Geographic distribution
        dimension: cases_by_district
      - type: epi_curve
        title: Cases over time
        dataset: case_reports
        date_field: report_date
        value_field: cases

ui:
  theme: light
  locale: en
  translations: {{}}

plugins: []
"""

README_TEMPLATE = """# {title}

This public-health application was created with PHFrame.

## Run

```bash
phframe check
phframe migrate
phframe serve
```

Open <http://127.0.0.1:8000/app> and inspect API metadata at
<http://127.0.0.1:8000/api>.

Edit `phframe.yaml` to customize datasets and fields.

Indicator results are available at `/api/indicators/{{name}}` and data-quality
results at `/api/data-quality`.
Saved filters are listed at `/api/filters`; grouped dimensions are available at
`/api/dimensions/{{name}}`.
Surveillance thresholds are evaluated at `/api/thresholds/{{name}}`.
Generated case reports use reusable public-health identifier, disease-code, age,
and epidemiological-week field types.
Organisation-unit hierarchy metadata is available at `/api/organisation-units`.

## Import records

```bash
phframe import case_reports records.xlsx --dry-run
phframe import case_reports records.xlsx --save-mapping mappings/case-reports.yaml
phframe imports
```
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
    (root / "mappings").mkdir(exist_ok=True)
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
    messages.append(f"Indicators: {len(config.indicators)}")
    messages.append(f"Data-quality rules: {len(config.data_quality_rules)}")
    messages.append(f"Saved filters: {len(config.saved_filters)}")
    messages.append(f"Dimensions: {len(config.dimensions)}")
    messages.append(f"Thresholds: {len(config.thresholds)}")
    messages.append(f"Organisation units: {len(config.organisation_units)}")
    messages.append(f"Dashboards: {len(config.dashboards)}")
    messages.append(f"UI: {config.ui.theme}, {config.ui.locale}")
    messages.append(f"Environment: {config.environment}")
    messages.append(f"Database: {config.database_display}")
    Storage(config).initialize()
    messages.append("Database: ready")
    if config.environment == "production" and config.database.startswith("sqlite:///"):
        messages.append("Warning: PostgreSQL is recommended for multi-user production deployments")
    messages.append("System check passed")
    return config, messages
