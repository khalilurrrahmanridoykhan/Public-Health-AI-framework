# Public Health Framework

Public Health Framework is an early-stage command-line toolkit that turns CSV or Excel exports into a portable HTML dashboard. It is designed for recurring surveillance and program-reporting workflows where teams currently rebuild the same summaries in spreadsheets.

## Current MVP

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

## Quick start

Use the guided workflow:

```bash
phdash analyze examples/malaria_surveillance.csv --interactive --open
```

Or provide the column roles directly, which is useful for automation:

```bash
phdash analyze examples/malaria_surveillance.csv \
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
phdash analyze monthly-report.xlsx --sheet Surveillance --interactive
```

Run `phdash analyze --help` for all options.

## Development

```bash
pytest
```

## Roadmap

1. Reusable indicator definitions (positivity, incidence, coverage, and dropout)
2. Geographic maps using administrative boundary files
3. Saved project configuration for repeat monthly runs
4. KoboToolbox and DHIS2 connectors
5. PDF and PowerPoint report export
6. JavaScript package and optional local web interface

## License

MIT

