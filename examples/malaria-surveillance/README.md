# Malaria Surveillance (reference application)

This is PHFrame's reference application: a complete, runnable project
demonstrating every capability in the [first vertical slice](../../PLAN.md)
on a single, realistic surveillance use case — monthly malaria case and
testing counts reported by facilities in five districts.

It is a normal PHFrame project; nothing here is special-cased by the
framework. Copy this directory as a starting point for a real deployment,
or read `phframe.yaml` alongside [`docs/configuration.md`](../../docs/configuration.md)
to see how each requirement maps to a declarative configuration section.

## Run it

```bash
cd examples/malaria-surveillance
phframe check
phframe import facility_reports ../malaria_surveillance.csv
phframe serve
```

Open <http://127.0.0.1:8000/app> for the Web Component application, or
inspect the generated API at <http://127.0.0.1:8000/api>.

## What it demonstrates

| Vertical-slice requirement | Where |
|---|---|
| A malaria case-reporting schema | `datasets.facility_reports` |
| CSV import | `phframe import facility_reports ../malaria_surveillance.csv` |
| SQLite storage | `project.database` (the default) |
| Validated CRUD and aggregate APIs | generated automatically for `facility_reports` |
| A filterable surveillance report line list | `/app#/records` and `GET /api/facility_reports` |
| Incidence and test positivity | `indicators.incidence_per_100000`, `indicators.test_positivity_percentage` |
| An epidemiological curve | the `epi_curve` widget in `dashboards.main` |
| Data-quality rules | `data_quality.cases_nonnegative`, `.tested_nonnegative`, `.valid_facility_type` |
| A surveillance alert threshold | `thresholds.high_incidence` |
| An AI-assisted summary with audit history | `/app#/ai`, available on every PHFrame project once data is imported |

The sample data is synthetic; see
[docs/data-provenance.md](../../docs/data-provenance.md).
`tests/test_reference_application.py` imports it and checks every indicator,
data-quality rule, and threshold above against the actual values in the
file, so this table stays accurate.
