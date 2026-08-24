# PHFrame

[![CI](https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

PHFrame is an early-stage framework for building extensible public-health data systems. Phase 1 introduces generated projects, declarative dataset schemas, persistent storage, and automatic APIs. The original CSV/Excel dashboard generator remains available as an export workflow.

> Current version: `0.2.0a1` (Phase 1 foundation preview)

## Why PHFrame?

Public-health teams often begin with spreadsheets and later need validated imports, persistent storage, audit history, and APIs. PHFrame provides a progressive path from those files to a configurable application while keeping the data model explicit.

Current capabilities include:

- Declarative datasets and validation in `phframe.yaml`
- Generated CRUD APIs backed by SQLite or PostgreSQL
- Atomic CSV and Excel imports with reusable column mappings
- Import audit history and safe schema migration checks
- Portable HTML dashboards for offline sharing
- Declarative indicators with count, sum, average, rate, ratio, and percentage calculations

> [!IMPORTANT]
> PHFrame is alpha software. Evaluate it with non-sensitive data before considering production use. It does not yet provide authentication or a complete deployment security model.

## Create a public-health application

```bash
phframe new "Malaria Surveillance"
cd malaria-surveillance
phframe check
phframe serve
```

Open <http://127.0.0.1:8000>. The generated project includes:

- `phframe.yaml` — project, database, dataset, field, and plugin configuration
- `data/phframe.db` — local SQLite database
- `plugins/` — application-specific extension modules
- `/api` — discoverable dataset metadata
- `/api/case_reports` — generated collection API
- `/api/case_reports/{id}` — generated record API

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/case_reports \
  -H 'content-type: application/json' \
  -d '{
    "case_id": "MAL-001",
    "disease": "Malaria",
    "status": "confirmed",
    "report_date": "2026-07-21",
    "district": "Bandarban",
    "cases": 1
  }'
```

The Phase 1 schema supports `string`, `integer`, `number`, `boolean`, `date`, `datetime`, and `location` fields, plus `required` and `protected` metadata.

## Indicators

Define deterministic indicators alongside datasets in `phframe.yaml`:

```yaml
indicators:
  total_cases:
    dataset: case_reports
    operation: sum
    field: cases
    date_field: report_date
  incidence_per_100000:
    dataset: case_reports
    operation: rate
    numerator: cases
    denominator: population
    multiplier: 100000
    date_field: report_date
```

Retrieve results through the generated API:

```bash
curl 'http://127.0.0.1:8000/api/indicators/total_cases'
curl 'http://127.0.0.1:8000/api/indicators/total_cases?district=Bandarban'
curl 'http://127.0.0.1:8000/api/indicators/total_cases?start=2026-07-01&end=2026-07-31'
curl 'http://127.0.0.1:8000/api/indicators/total_cases?period=2026-W30'
```

The supported operations are `count`, `sum`, `average`, `rate`, `ratio`, and `percentage`. Rate, ratio, and percentage indicators return `null` when the summed denominator is zero.

Named periods accept ISO epidemiological weeks (`2026-W30`), calendar months (`2026-07`), and quarters (`2026-Q3`).

## Data-quality rules

Configure completeness, numeric range, and allowed-value checks without changing imported records:

```yaml
data_quality:
  cases_nonnegative:
    dataset: case_reports
    field: cases
    check: range
    min: 0
  valid_case_status:
    dataset: case_reports
    field: status
    check: allowed
    values: [suspected, probable, confirmed]
```

`GET /api/data-quality` evaluates every rule. `GET /api/data-quality/{rule}` returns its record count, valid count, violation count, and percentage score.

## Saved filters and dimensions

Reusable filters keep common cohorts consistent across indicators and grouped summaries:

```yaml
filters:
  confirmed_cases:
    dataset: case_reports
    values:
      status: confirmed

dimensions:
  confirmed_cases_by_district:
    dataset: case_reports
    field: district
    filter: confirmed_cases
```

Apply a saved filter with `GET /api/indicators/total_cases?filter=confirmed_cases`. Dimension results are available from `GET /api/dimensions/{name}` and return each distinct value with its record count. Request fields can override saved filter values when an ad hoc refinement is needed.

## Schema migrations

PHFrame tracks the configured dataset schemas in the project database. Preview safe changes with:

```bash
phframe migrate --check
```

Apply them with:

```bash
phframe migrate
```

Adding optional fields is automatic. PHFrame refuses destructive field removal, incompatible type changes, and new required fields that would invalidate existing records.

## Persistent data imports

Validate an import without writing records:

```bash
phframe import case_reports monthly-cases.xlsx --dry-run
```

If spreadsheet headings already match dataset fields, import directly:

```bash
phframe import case_reports monthly-cases.xlsx
```

Map different source headings and save the mapping for future reporting periods:

```bash
phframe import case_reports monthly-cases.xlsx \
  --map 'Case Number=case_id' \
  --map 'Disease Name=disease' \
  --map 'Classification=status' \
  --map 'Reported=report_date' \
  --map 'Area=district' \
  --map 'Case Count=cases' \
  --save-mapping mappings/case-reports.yaml
```

Reuse it later:

```bash
phframe import case_reports next-month.xlsx --mapping mappings/case-reports.yaml
phframe imports
```

Imports are atomic: PHFrame validates every row before inserting anything. Each validation or import attempt is recorded in the internal audit history and exposed at `GET /api/imports`.

## Development and production configuration

Generated projects use SQLite for local development. Paths in SQLite URLs are resolved relative to `phframe.yaml`:

```yaml
project:
  name: Malaria Surveillance
  database: sqlite:///data/phframe.db
  environment: development

server:
  host: 127.0.0.1
  port: 8000
```

Start the development server with automatic reload:

```bash
phframe serve --reload
```

For PostgreSQL, install the optional driver:

```bash
pip install 'public-health-framework[postgres]'
```

Keep production credentials outside source control:

```bash
export PHFRAME_ENV=production
export PHFRAME_DATABASE_URL='postgresql+psycopg://user:password@localhost/phframe'
export PHFRAME_HOST=0.0.0.0
export PHFRAME_PORT=8000

phframe check
phframe migrate
phframe serve
```

Alternatively, `phframe.yaml` can refer to an environment variable:

```yaml
project:
  database: ${DATABASE_URL}
```

PHFrame redacts database credentials in system-check output. SQLite and PostgreSQL use the same dataset, CRUD, import-audit, and migration APIs. Reload mode is intentionally disabled when `PHFRAME_ENV=production`.

## Dashboard export

- Reads `.csv`, `.xlsx`, and `.xlsm` files
- Supports an interactive column-selection wizard
- Recognizes location, date, measured value, population, and category roles
- Calculates record count, completeness, totals, and rates per 100,000
- Generates grouped summaries, monthly trends, a data-quality table, and a data preview
- Writes one responsive HTML file that can be emailed or opened without a server

## Install for development

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Quick start

Use the guided workflow:

```bash
phframe analyze examples/malaria_surveillance.csv --interactive --open
```

Or provide the column roles directly, which is useful for automation:

```bash
phframe analyze examples/malaria_surveillance.csv \
  --location district \
  --date report_date \
  --value cases \
  --population population \
  --category facility_type \
  --title "Malaria Surveillance Dashboard" \
  --output malaria-dashboard.html
```

For an Excel workbook, use `--sheet 0` (the default), `--sheet 1`, or a sheet name:

```bash
phframe analyze monthly-report.xlsx --sheet Surveillance --interactive
```

Run `phframe analyze --help` for all options.

## Development

```bash
pytest
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [SECURITY.md](SECURITY.md) for responsible vulnerability reporting.

## Project status

PHFrame follows semantic versioning after the `0.2.0a1` preview. See [CHANGELOG.md](CHANGELOG.md) for release notes and [PLAN.md](PLAN.md) for the full architecture and phased roadmap.

## Roadmap

See [PLAN.md](PLAN.md) for the full architecture and phased roadmap.

## License

MIT
