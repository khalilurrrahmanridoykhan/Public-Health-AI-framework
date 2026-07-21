# PHFrame

PHFrame is an early-stage framework for building extensible public-health data systems. Phase 1 introduces generated projects, declarative dataset schemas, persistent storage, and automatic APIs. The original CSV/Excel dashboard generator remains available as an export workflow.

> Current version: `0.2.0a1` (Phase 1 foundation preview)

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

## Roadmap

See [PLAN.md](PLAN.md) for the full architecture and phased roadmap.

## License

MIT
