# Data provenance

| File | Source | Created / accessed | Transformations | License |
|---|---|---|---|---|
| `examples/malaria_surveillance.csv` | Synthetic data written by the PHFrame maintainers for demonstrations and tests | 2026 (tracked in git history) | None; values entered by hand | MIT, same as the project |
| `examples/case_reports.csv` | Synthetic data written by the PHFrame maintainers for demonstrations and tests | 2026 (tracked in git history) | None; values entered by hand | MIT, same as the project |

## Notes

- **Not real surveillance data.** Case counts, test counts, and case identifiers are invented. They must not be used for analysis, reporting, or decisions.
- **Place names** are real Bangladesh districts and divisions, chosen so maps and hierarchies look realistic. **Population figures** are rounded illustrative values, not official census estimates.
- **No personal data.** The files contain no names, contact details, or other information about real people.
- **Changes** to these files are recorded in git history. Any future file taken from an external source must add a row here with its source URL, access date, transformations, and license.

Variable definitions are in [data-dictionary.md](data-dictionary.md).
