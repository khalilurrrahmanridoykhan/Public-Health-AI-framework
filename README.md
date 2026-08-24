# PHFrame

<img src="src/public_health_framework/ui/phframe-logo.png" alt="PHFrame logo" width="112">

[![CI](https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

PHFrame is an early-stage framework for building extensible public-health data systems. It combines generated projects, declarative health schemas, persistent storage, automatic APIs, a public-health engine, and a standards-based Web Component interface. The original CSV/Excel dashboard generator remains available as an export workflow.

> Current version: `0.7.0a4` (branded workspace and access-control preview)

## Why PHFrame?

Public-health teams often begin with spreadsheets and later need validated imports, persistent storage, audit history, and APIs. PHFrame provides a progressive path from those files to a configurable application while keeping the data model explicit.

Current capabilities include:

- Declarative datasets and validation in `phframe.yaml`
- Generated CRUD APIs backed by SQLite or PostgreSQL
- Atomic CSV, Excel, JSON, and XML imports with reusable column mappings
- Import audit history and safe schema migration checks
- Portable HTML dashboards for offline sharing
- Declarative indicators with count, sum, average, rate, ratio, and percentage calculations
- Drag-resizable dashboards with add/remove controls and browser-saved visualization choices
- Browser-managed typed columns for worldwide, programme-specific data models
- Browser imports with downloadable examples and scheduled generic API, DHIS2, KoboToolbox, and ODK synchronization
- Editable branding, navigation, footer, themes, primary color, dashboard title, logo, and favicon
- Optional private mode with PBKDF2-hashed local user credentials and signed, HTTP-only login sessions

> [!IMPORTANT]
> PHFrame is alpha software. Evaluate it with non-sensitive data before considering production use. It does not yet provide authentication or a complete deployment security model.

## Create a public-health application

```bash
phframe new "Malaria Surveillance"
cd malaria-surveillance
phframe check
phframe serve
```

Open <http://127.0.0.1:8000/app> for the application interface. The generated project includes:

- `phframe.yaml` — project, database, dataset, field, and plugin configuration
- `data/phframe.db` — local SQLite database
- `plugins/` — application-specific extension modules
- `/api` — discoverable dataset metadata
- `/api/case_reports` — generated collection API
- `/api/case_reports/{id}` — generated record API
- `/app` — responsive Web Component application

## Web Component application

The Phase 3 interface is served directly by PHFrame and has no React or external CDN dependency. It includes:

- Hash-based application routing and a responsive application shell
- Metadata-driven record forms and protected-field-aware tables
- Saved filters and organisation-unit selection
- KPI cards, grouped SVG charts, epidemiological curves, and offline tile choropleths
- Declarative dashboard composition in `phframe.yaml`
- Light, dark, and high-contrast themes using CSS design tokens
- English and Bengali localization foundations with project-specific translation overrides
- Keyboard focus styling, skip navigation, reduced-motion support, live notifications, modal dialogs, and confirmations

Configure the interface and dashboard:

```yaml
ui:
  theme: light
  locale: en
  translations: {}

dashboards:
  main:
    label: Malaria Surveillance Dashboard
    widgets:
      - type: kpi
        title: Total cases
        indicator: total_cases
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
```

## Browser imports

The browser import workspace accepts `.csv`, `.xlsx`, `.xlsm`, `.json`, and `.xml`.
It provides downloadable examples for the selected dataset before upload. JSON may
be an array of objects or contain a `data`, `records`, `results`, or `items` array;
XML uses a root element containing one child element per record.

Use **Data builder** in the application to add optional typed columns. Additions
are migrated safely and persisted to `phframe.yaml`; existing records are retained.

Dashboard cards can be reordered and resized, removed or restored, and switched
between appropriate number, gauge, bar, donut, line, column, tile, and table views.
Use **Add visualization** to chart configured indicators, dimensions, or any typed
numeric, categorical, and date field. Layout choices are stored in the browser.

Resize cards from any edge or corner. The grid span, height, chart layout, legend,
and content overflow adapt together; mobile layouts continue to collapse to a
single column.

## Branding and access settings

Open **Settings** to edit the product name, header title, dashboard title,
navigation labels and visibility, footer, primary color, default theme, logo,
and favicon. Uploaded assets are stored in the project's ignored `data/branding/`
directory, so each deployment can have independent branding.

Projects are public by default. To enable private mode, create a username and a
password of at least 10 characters in Settings and select **Private**. Passwords
use PBKDF2-HMAC-SHA256 with per-user salts, and browser sessions use signed,
HTTP-only, same-site cookies. Use HTTPS in any networked deployment. This local
alpha authentication is appropriate for evaluation and controlled deployments;
SSO, roles, account recovery, audit controls, and production hardening remain
future work.

Open `/app#/import` to import `.csv`, `.xlsx`, or `.xlsm` files through a guided workflow:

1. Select the target dataset and file.
2. Preview up to ten rows.
3. Map source columns to typed dataset fields.
4. Save the mapping as a reusable server-side template.
5. Validate without writing, or import all rows atomically.
6. Inspect row-level failures through the import run error API.

Browser uploads are limited to 25 MB. `GET /api/import-mappings` lists reusable mappings, and `GET /api/imports/{run_id}/errors` provides structured error reports.

## DHIS2, KoboToolbox, and ODK connectors

The Connectors screen provides separate guided setup choices for generic JSON
REST APIs, DHIS2 data value sets, KoboToolbox assets, and ODK Central project/form
OData feeds. It can create, test, schedule, synchronize, and remove each connector.
Generic APIs accept a JSON array
or common record containers such as `data`, `records`, `results`, `items`, and
`value`. Source paths map into typed dataset fields; synchronized records then
become available to dashboard visualizations. Credentials are referenced through
environment-variable names and are never written into project configuration.

Connectors pull JSON records, apply nested source-to-dataset mappings, validate every record, and write atomically. Credentials are read only from environment variables and are never returned through metadata APIs.

Example KoboToolbox connector:

```yaml
connectors:
  kobo_cases:
    type: kobo
    dataset: case_reports
    base_url: https://kf.kobotoolbox.org
    resource: your_asset_uid
    schedule_minutes: 60
    auth:
      token_env: KOBO_TOKEN
    mapping:
      case_id: case_id
      disease: disease
      status: status
      report_date: report_date
      district: district
      cases: cases
```

DHIS2 uses `resource` as the data-set UID and reads `dataValues`; ODK uses `PROJECT_ID/FORM_ID` and reads the OData `Submissions` feed. Nested source fields use dot notation, such as `__system.submissionDate`.

```yaml
connectors:
  dhis2_values:
    type: dhis2
    dataset: aggregate_values
    base_url: https://play.dhis2.org/example
    resource: DATA_SET_UID
    auth:
      token_env: DHIS2_TOKEN
    parameters:
      period: 202608
      orgUnit: ORG_UNIT_UID
    mapping:
      dataElement: data_element
      period: period
      orgUnit: organisation_unit
      value: value

  odk_cases:
    type: odk
    dataset: case_reports
    base_url: https://central.example.org
    resource: 7/malaria_case
    auth:
      token_env: ODK_SESSION_TOKEN
    parameters:
      $top: 500
    mapping:
      meta.instanceID: case_id
      disease: disease
      status: status
      __system.submissionDate: report_date
      district: district
      cases: cases
```

Run connectors manually, validate them, or invoke due schedules from cron/systemd:

```bash
phframe sync kobo_cases
phframe sync kobo_cases --dry-run
phframe sync --all
phframe sync --all --due
phframe syncs --limit 50
```

`schedule_minutes` determines whether `--due` selects a connector; PHFrame records every completed, validated, or failed synchronization. The browser console at `/app#/connectors` exposes the same status and history. See the official [DHIS2 API authentication](https://docs.dhis2.org/en/develop/using-the-api/dhis-core-version-master/introduction.html), [KoboToolbox API v2 migration](https://support.kobotoolbox.org/migrating_api.html), and [ODK Central OData](https://docs.getodk.org/central-api-odata-endpoints/) documentation for provider-side setup.

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

The schema supports generic `string`, `integer`, `number`, `boolean`, `date`, `datetime`, and `location` fields, plus `required` and `protected` metadata.

Reusable public-health types add domain-aware storage and validation:

- `identifier`, `disease_code`, `organisation_unit`, and `facility` require non-empty text.
- `age` accepts whole years from 0 through 130.
- `sex` accepts `female`, `male`, `intersex`, or `unknown`.
- `case_classification` accepts `suspected`, `probable`, `confirmed`, or `discarded`.
- `epi_week` accepts ISO week values such as `2026-W33`.
- `reporting_period` accepts ISO weeks, calendar months, or quarters.

These types use portable text or integer database columns, so applications retain SQLite and PostgreSQL compatibility.

## Organisation-unit hierarchy

Declare reporting structures with stable codes and parent relationships:

```yaml
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
```

`GET /api/organisation-units` lists the hierarchy and root codes. `GET /api/organisation-units/{code}` returns the unit with its children and ordered ancestors. Values written to `organisation_unit` fields must reference a configured code. PHFrame rejects missing parents and hierarchy cycles during configuration loading.

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

## Surveillance thresholds

Attach alert levels to deterministic indicators:

```yaml
thresholds:
  high_weekly_case_count:
    indicator: total_cases
    operator: gte
    value: 10
    severity: warning
    message: Weekly case count has reached the surveillance alert level.
```

Evaluate rules with `GET /api/thresholds` or `GET /api/thresholds/{name}`. The endpoints accept the same `period`, `filter`, `start`, `end`, and field-filter parameters as indicators and return `normal`, `triggered`, or `no_data`. Supported operators are `gt`, `gte`, `lt`, `lte`, and `eq`.

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
