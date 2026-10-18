# Data dictionary

This codebook describes the example datasets in [`examples/`](../examples). Both are CSV files, UTF-8 encoded, comma-separated, with one header row. Dates use ISO 8601 (`YYYY-MM-DD`).

**Missing values:** an empty cell means "not reported". The files do not use sentinel codes such as `NA`, `-1`, or `999`. Required fields are never empty.

## `examples/malaria_surveillance.csv`

Monthly aggregate malaria surveillance, one row per district per reporting month.

| Variable | Type | Unit | Required | Allowed values / constraints | Description |
|---|---|---|---|---|---|
| `district` | text | – | yes | Administrative area name | District or division reporting the data |
| `report_date` | date | – | yes | First day of the reporting month | Reporting period |
| `cases` | integer | cases | yes | ≥ 0 | Total malaria cases reported in the period |
| `population` | integer | people | yes | > 0 | Population of the area, used as the rate denominator |
| `confirmed_cases` | integer | cases | yes | 0 ≤ value ≤ `tested` | Cases confirmed by RDT or microscopy |
| `tested` | integer | people | yes | ≥ `confirmed_cases` | People tested for malaria in the period |
| `facility_type` | text | – | yes | `Hospital`, `Clinic`, `Community` | Type of reporting facility |

Derived indicators: incidence per 100,000 = `cases / population × 100000`; test positivity = `confirmed_cases / tested`.

## `examples/case_reports.csv`

Individual case line list matching the `case_reports` dataset created by `phframe new`.

| Variable | Type | Unit | Required | Allowed values / constraints | Description |
|---|---|---|---|---|---|
| `case_id` | identifier | – | yes | Unique; `<DISEASE>-<number>` | Case identifier, protected from edits |
| `disease` | disease code | – | yes | e.g. `Malaria`, `Dengue` | Reported disease |
| `status` | text | – | yes | `suspected`, `probable`, `confirmed` | Case classification |
| `onset_date` | date | – | no | ≤ `report_date` | Date symptoms started |
| `report_date` | date | – | yes | – | Date the case was reported |
| `district` | location | – | yes | Administrative area name | Area where the case was reported |
| `cases` | integer | cases | yes | ≥ 1 (line list rows are 1) | Number of cases the row represents |
| `population` | integer | people | no | > 0 | Population of the district, for rates |

The project schema also defines optional `country`, `patient_age` (whole years 0–130), `epi_week`, and `reporting_unit` fields that the example file leaves out.

See [data-provenance.md](data-provenance.md) for where these files come from.
