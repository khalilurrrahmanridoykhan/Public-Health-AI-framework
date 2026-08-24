# Changelog

All notable changes to PHFrame will be documented here. The project intends to follow [Semantic Versioning](https://semver.org/) after the alpha preview.

## [Unreleased]

- Add continuous integration across Python 3.10–3.12.
- Add contribution and security guidance.
- Improve package metadata and project documentation.
- Add declarative count, sum, average, rate, ratio, and percentage indicators.
- Add indicator metadata and result APIs with field filters and reporting-period ranges.
- Add total-cases and incidence indicators to newly generated surveillance projects.
- Add ISO-week, calendar-month, and quarter reporting periods to indicator queries.
- Add declarative completeness, numeric-range, and allowed-value data-quality rules.
- Add data-quality metadata and evaluation APIs.
- Add reusable saved filters for indicator and dimension queries.
- Add declarative dimensions with grouped-count APIs.
- Add declarative surveillance thresholds with severity and alert messages.
- Add threshold evaluation APIs that support periods and saved filters.
- Add reusable identifier, disease-code, age, sex, case-classification, epidemiological-week, reporting-period, organisation-unit, and facility field types.
- Add domain validation and portable storage mappings for public-health field types.
- Add declarative organisation-unit hierarchies with parent and cycle validation.
- Add hierarchy discovery APIs and organisation-unit referential validation for record writes and imports.

## [0.2.0a1] - 2026-07-21

### Added

- Generated projects with declarative dataset schemas.
- SQLite and PostgreSQL persistence.
- Generated collection and record APIs.
- Safe schema migration checks.
- Atomic CSV and Excel imports with saved column mappings.
- Import audit history.
- Portable HTML dashboard export.

[Unreleased]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.2.0a1...HEAD
[0.2.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/releases/tag/v0.2.0a1
